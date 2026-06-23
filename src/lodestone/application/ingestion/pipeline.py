"""The ingestion pipeline (application core).

Composes the dependency-free kag compute stages into:

    read -> split -> extract -> vectorize -> postprocess(filter)  ->  SubGraph

It depends on the two driven ports (LanguageModelPort, EmbeddingModelPort) for
its external resources; everything else is internal composition. No graph store,
no API. The pipeline is built once (loads schema + prompt templates) and reused.

Concurrency: the IO-bound file read runs in a worker thread (``asyncio.to_thread``)
and the per-chunk extractions run concurrently (``asyncio.gather``). The model
HTTP calls themselves are issued synchronously *inside* kag, which we
treat as frozen, so they block the loop for their duration — a known limitation
to address at the adapter boundary if needed.
"""

from __future__ import annotations

import asyncio

from kag.builder.component.extractor.schema_free_extractor import (
    SchemaFreeExtractor,
)
from kag.builder.component.postprocessor.kag_postprocessor import (
    KAGPostProcessor,
)
from kag.builder.component.reader.txt_reader import TXTReader
from kag.builder.component.splitter.length_splitter import LengthSplitter
from kag.builder.component.vectorizer.batch_vectorizer import BatchVectorizer
from kag.builder.model.chunk import Chunk
from kag.builder.model.sub_graph import SubGraph

# vendored compute library
from kag.interface import LLMClient, VectorizeModelABC
from src.lodestone.domain.ports.ingestion import EmbeddingModelPort, LanguageModelPort


class IngestionPipeline:
    def __init__(
        self,
        llm: LanguageModelPort,
        embedder: EmbeddingModelPort,
        schema_path: str,
        language: str = "en",
        split_length: int = 500,
        window_length: int = 100,
    ) -> None:
        # bind the ports into the library's seams (call/vectorize)
        self._llm = LLMClient(call=lambda prompt, **_: llm.complete(prompt))
        self._embed = VectorizeModelABC(vectorize=lambda texts: embedder.embed(texts))

        # build the stages once (schema load + prompt templates are expensive)
        self._reader = TXTReader()
        self._splitter = LengthSplitter(
            split_length=split_length, window_length=window_length, language=language
        )
        self._extractor = SchemaFreeExtractor(
            llm=self._llm, schema_path=schema_path, language=language
        )
        self._vectorizer = BatchVectorizer(vectorize_model=self._embed, schema_path=schema_path)
        self._postprocessor = KAGPostProcessor(schema_path=schema_path)  # filter-only

    async def ingest(self, source: str) -> SubGraph:
        """Ingest a document (a file path or raw text) into a SubGraph."""
        # read (IO-bound) + split run off the event loop in one thread hop
        chunks = await asyncio.to_thread(self._read_and_split, source)

        # extract a SubGraph per chunk concurrently, then merge
        subgraph_lists = await asyncio.gather(
            *(self._extractor._ainvoke(chunk) for chunk in chunks)
        )
        merged = SubGraph(nodes=[], edges=[])
        for subgraphs in subgraph_lists:
            for subgraph in subgraphs:
                merged.merge(subgraph)

        # embed vector-indexed fields via the vectorizer's async path
        merged = (await self._vectorizer._ainvoke(merged))[0]

        # filter invalid nodes/edges off the event loop (linking off — no store)
        merged = (await asyncio.to_thread(self._postprocessor._invoke, merged))[0]
        return merged

    def ingest_sync(self, source: str) -> SubGraph:
        """Blocking convenience wrapper around ``ingest`` for non-async callers."""
        return asyncio.run(self.ingest(source))

    def _read_and_split(self, source: str) -> list[Chunk]:
        """Read the source and split it into retrieval-sized chunks (sync)."""
        chunks: list[Chunk] = []
        for doc_chunk in self._reader.invoke(source):
            chunks.extend(self._splitter._invoke(doc_chunk))
        return chunks
