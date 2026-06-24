"""The ingestion pipeline (application core).

Composes the dependency-free kag_extracted compute stages into:

    read -> split -> extract -> vectorize -> postprocess(filter)  ->  SubGraph

It depends on the two driven ports (LanguageModelPort, EmbeddingModelPort) for
its external resources; everything else is internal composition. No graph store,
no API. The pipeline is built once (loads schema + prompt templates) and reused.

Concurrency: the IO-bound file read runs in a worker thread (``asyncio.to_thread``)
and the per-chunk extractions run concurrently (``asyncio.gather``). The model
HTTP calls themselves are issued synchronously *inside* kag_extracted, which we
treat as frozen, so they block the loop for their duration — a known limitation
to address at the adapter boundary if needed.
"""

from __future__ import annotations

import asyncio

from kag.builder.component.extractor.schema_constraint_extractor import (
    SchemaConstraintExtractor,
)
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
from kag.builder.prompt.spg_prompt import (
    SPGEntityPrompt,
    SPGEventPrompt,
    SPGRelationPrompt,
)

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
        extraction_mode: str = "schema_constraint",
    ) -> None:
        # bind the ports into the library's seams (call/vectorize)
        self._llm = LLMClient(call=lambda prompt, **_: llm.complete(prompt))
        self._embed = VectorizeModelABC(vectorize=lambda texts: embedder.embed(texts))

        # build the stages once (schema load + prompt templates are expensive)
        self._reader = TXTReader()
        self._splitter = LengthSplitter(
            split_length=split_length, window_length=window_length, language=language
        )
        self._extractor = self._build_extractor(extraction_mode, schema_path, language)
        self._vectorizer = BatchVectorizer(vectorize_model=self._embed, schema_path=schema_path)
        self._postprocessor = KAGPostProcessor(schema_path=schema_path)  # filter-only

    def _build_extractor(self, mode: str, schema_path: str, language: str):
        """Build the extractor for the requested mode.

        ``schema_constraint`` mirrors the server: the SPG entity/relation/event
        prompts inject the schema (types, properties, constraints) so the LLM
        extracts conforming entities and typed relations. ``schema_free`` keeps
        the open-IE NER + triple extraction (type vocabulary only).
        """
        if mode == "schema_free":
            return SchemaFreeExtractor(llm=self._llm, schema_path=schema_path, language=language)
        if mode == "schema_constraint":
            return SchemaConstraintExtractor(
                llm=self._llm,
                schema_path=schema_path,
                language=language,
                ner_prompt=SPGEntityPrompt(language=language, schema_path=schema_path),
                relation_prompt=SPGRelationPrompt(language=language, schema_path=schema_path),
                event_prompt=SPGEventPrompt(language=language, schema_path=schema_path),
            )
        raise ValueError(
            f"unknown extraction_mode {mode!r}; expected 'schema_constraint' or 'schema_free'"
        )

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
