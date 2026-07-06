from __future__ import annotations

import asyncio
from contextlib import contextmanager

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
from kag.builder.component.splitter.length_splitter import LengthSplitter
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
from src.lodestone.exceptions import (
    ChunkingError,
    DocumentReadError,
    EmbeddingError,
    ExtractionError,
    GraphStoreError,
    LodestoneError,
)


class IngestionPipeline:
    """Ingest documents into the Neo4j knowledge graph.

    Wires the kag builder stages (read, split, extract, align, vectorize,
    post-process, write) into a single async flow, translating stage failures
    into typed domain errors.
    """

    def __init__(
        self,
        llm: LLMClient,
        embedder: VectorizeModelABC,
        schema_path: str,
        graph_store,
        extractors: list | None = None,
        similarity_threshold: float = 0.9,
        namespace: str = "",
    ) -> None:
        # kag clients (BedrockClaudeClient, BedrockCohereVectorizeModel) are the
        # model seams the kag components are written against; used directly.
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

        # 2) splitter: sliding-window split by character length. No LLM call, so
        #    it sidesteps the Bedrock RPM ceiling that made the per-node
        #    SemanticSplitter throttle out (ChunkingError). The docx reader
        #    already emits one chunk per clause via its heading tree, so semantic
        #    boundaries are largely set before the splitter runs; this stage only
        #    caps oversized chunks. Table-aware via BaseTableSplitter.
        self._splitter = LengthSplitter(split_length=1500, window_length=150)

        # 3) extractors (run concurrently per chunk). When ``extractors`` is
        #    supplied (the index_list-driven path: each active KAGIndexManager
        #    contributes its extractor via build_extractor_config), those are
        #    used. Otherwise fall back to the default schema_constraint + summary
        #    pair, so direct callers and tests keep working unchanged.
        self._extractors = (
            extractors
            if extractors is not None
            else [
                SchemaConstraintExtractor(
                    llm=self._llm,
                    schema_path=schema_path,
                    ner_prompt=SPGEntityPrompt(schema_path=schema_path),
                    relation_prompt=SPGRelationPrompt(schema_path=schema_path),
                    event_prompt=SPGEventPrompt(schema_path=schema_path),
                ),
                SummaryExtractor(llm_module=self._llm),
            ]
        )

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

    @contextmanager
    def _stage(self, error_cls: type[LodestoneError], message: str, source: str):
        """Translate any failure inside a pipeline stage into a typed domain error.

        Raw kag/third-party exceptions are wrapped (with ``from err`` so the
        original traceback is preserved); errors already translated upstream
        (e.g. read vs split) pass through unchanged.
        """
        try:
            yield
        except LodestoneError:
            raise
        except Exception as err:
            raise error_cls(message, details={"source": source}) from err

    async def ingest(self, source: str) -> SubGraph:
        """Ingest a document (file path, or a dict for dict_reader) into the graph."""
        # read (IO/LLM-bound) + semantic split run off the event loop
        chunks = await asyncio.to_thread(self._read_and_split, source)

        # extract every chunk with every extractor, concurrently but bounded so
        # we stay under Bedrock's request rate limit, then merge + de-dup
        with self._stage(ExtractionError, "extraction failed", source):
            sem = asyncio.Semaphore(2)

            async def _extract(extractor, chunk):
                async with sem:
                    return await extractor.ainvoke(chunk)

            subgraph_lists = await asyncio.gather(
                *(_extract(extractor, chunk) for chunk in chunks for extractor in self._extractors)
            )
            all_subgraphs = [sg for subgraphs in subgraph_lists for sg in subgraphs]
            merged = await asyncio.to_thread(self._aligner.invoke, all_subgraphs)

        # embed index-marked fields (real async vectorizer)
        with self._stage(EmbeddingError, "embedding failed", source):
            merged = (await self._vectorizer.ainvoke(merged))[0]

        # filter + entity-link against the graph store, off the event loop
        with self._stage(GraphStoreError, "post-processing / entity linking failed", source):
            merged = (await asyncio.to_thread(self._postprocessor.invoke, merged))[0]

        # persist to Neo4j
        with self._stage(GraphStoreError, "failed to persist graph", source):
            await asyncio.to_thread(self._writer.invoke, merged)

        return merged

    def ingest_sync(self, source: str) -> SubGraph:
        """Blocking convenience wrapper around ``ingest`` for non-async callers."""
        return asyncio.run(self.ingest(source))

    def _read_and_split(self, source: str) -> list[Chunk]:
        """Read the source (extension-routed) and semantically split it (sync)."""
        try:
            documents = self._reader.invoke(source)
        except Exception as err:
            raise DocumentReadError("failed to read document", details={"source": source}) from err

        chunks: list[Chunk] = []
        try:
            for document in documents:
                chunks.extend(self._splitter.invoke(document))
        except Exception as err:
            raise ChunkingError("failed to split document", details={"source": source}) from err
        return chunks
