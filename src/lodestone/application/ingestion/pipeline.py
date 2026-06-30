"""Production ingestion pipeline (application core).

Composes the kag compute stages into a fully async knowledge-graph build:

    read (MixReader)            # auto-routes txt/pdf/docx/md/dict by extension
      -> split (SemanticSplitter)
      -> extract (schema_constraint + summary, run concurrently per chunk)
      -> align (KAGAligner: merge + de-duplicate the per-chunk subgraphs)
      -> vectorize (BatchVectorizer: embed index-marked fields)
      -> post-process (KAGPostProcessor: filter + Neo4j entity linking)
      -> write (GraphStoreWriter -> Neo4j)

The LLM (a kag ``LLMClient``, e.g. AzureOpenAIClient) is shared by the readers, the
semantic splitter, and the extractors. Embeddings use a kag ``VectorizeModelABC``
(e.g. AzureCohereVectorizeModel). A bound ``graph_store`` (Neo4jClient) is required:
the post-processor links entities against it and the writer persists into it.

Concurrency: IO/CPU-bound steps (read+split, post-process, write) run via
``asyncio.to_thread``; the per-chunk extractions run concurrently with
``asyncio.gather``.
"""

from __future__ import annotations

import asyncio

from kag.builder.component.aligner.kag_aligner import KAGAligner
from kag.builder.component.extractor.schema_constraint_extractor import (
    SchemaConstraintExtractor,
)
from kag.builder.component.extractor.summary_extractor import SummaryExtractor
from kag.builder.component.postprocessor.kag_postprocessor import KAGPostProcessor
from kag.builder.component.reader.dict_reader import DictReader
from kag.builder.component.reader.docx_reader import DocxReader
from kag.builder.component.reader.markdown_reader import MarkDownReader
from kag.builder.component.reader.mix_reader import MixReader
from kag.builder.component.reader.pdf_reader import PDFReader
from kag.builder.component.reader.txt_reader import TXTReader
from kag.builder.component.splitter.semantic_splitter import SemanticSplitter
from kag.builder.component.vectorizer.batch_vectorizer import BatchVectorizer
from kag.builder.component.writer.graph_store_writer import GraphStoreWriter
from kag.builder.model.chunk import Chunk
from kag.builder.model.sub_graph import SubGraph
from kag.builder.prompt.spg_prompt import (
    SPGEntityPrompt,
    SPGEventPrompt,
    SPGRelationPrompt,
)
from kag.common.tools.search_api.impl.neo4j_search_client import Neo4jSearchClient
from kag.interface import LLMClient, VectorizeModelABC
from kag.schema.client import SchemaClient


class IngestionPipeline:
    def __init__(
        self,
        llm: LLMClient,
        embedder: VectorizeModelABC,
        schema_path: str,
        graph_store,
        similarity_threshold: float = 0.9,
        namespace: str = "",
    ) -> None:
        # kag clients (AzureOpenAIClient, AzureCohereVectorizeModel) are the model
        # seams the kag components are written against; used directly.
        self._llm = llm
        self._embed = embedder

        # 1) reader: auto-routes by file extension (txt/pdf/docx/md) or dict input.
        self._reader = MixReader(
            txt_reader=TXTReader(),
            pdf_reader=PDFReader(llm=self._llm),
            docx_reader=DocxReader(llm=self._llm),
            md_reader=MarkDownReader(),
            dict_reader=DictReader(),
        )

        # 2) splitter: LLM-driven semantic segmentation (English prompts by default).
        self._splitter = SemanticSplitter(llm=self._llm)

        # 3) extractors (run concurrently per chunk):
        #    - schema_constraint: typed entities / relations / events (legal domain)
        #    - summary: one condensed Summary node per chunk (summary index)
        self._extractors = [
            SchemaConstraintExtractor(
                llm=self._llm,
                schema_path=schema_path,
                ner_prompt=SPGEntityPrompt(schema_path=schema_path),
                relation_prompt=SPGRelationPrompt(schema_path=schema_path),
                event_prompt=SPGEventPrompt(schema_path=schema_path),
            ),
            SummaryExtractor(llm_module=self._llm),
        ]

        # 4) align: merge + de-duplicate per-chunk subgraphs (kag logic).
        self._aligner = KAGAligner()

        # 5) vectorize: embed index-marked fields.
        self._vectorizer = BatchVectorizer(vectorize_model=self._embed, schema_path=schema_path)

        # 6) post-process: filter invalid nodes/edges + Neo4j entity linking.
        self._postprocessor = KAGPostProcessor(
            schema_path=schema_path,
            namespace=namespace,
            similarity_threshold=similarity_threshold,
            search_client=Neo4jSearchClient(graph_store),
        )

        # 7) write: persist the SubGraph to Neo4j.
        schema = SchemaClient(schema_path=schema_path).load()
        self._writer = GraphStoreWriter(graph_store, schema=schema, namespace=namespace)

    async def ingest(self, source: str) -> SubGraph:
        """Ingest a document (file path, or a dict for dict_reader) into the graph."""
        # read (IO/LLM-bound) + semantic split run off the event loop
        chunks = await asyncio.to_thread(self._read_and_split, source)

        # extract every chunk with every extractor, concurrently
        subgraph_lists = await asyncio.gather(
            *(extractor.ainvoke(chunk) for chunk in chunks for extractor in self._extractors)
        )
        all_subgraphs = [sg for subgraphs in subgraph_lists for sg in subgraphs]

        # align (merge + de-dup) off the loop, then embed (real async vectorizer)
        merged = await asyncio.to_thread(self._aligner.invoke, all_subgraphs)
        merged = (await self._vectorizer.ainvoke(merged))[0]

        # filter + entity-link off the event loop
        merged = (await asyncio.to_thread(self._postprocessor.invoke, merged))[0]

        # persist to Neo4j
        await asyncio.to_thread(self._writer.invoke, merged)
        return merged

    def ingest_sync(self, source: str) -> SubGraph:
        """Blocking convenience wrapper around ``ingest`` for non-async callers."""
        return asyncio.run(self.ingest(source))

    def _read_and_split(self, source: str) -> list[Chunk]:
        """Read the source (extension-routed) and semantically split it (sync)."""
        chunks: list[Chunk] = []
        for doc_chunk in self._reader.invoke(source):
            chunks.extend(self._splitter.invoke(doc_chunk))
        return chunks
