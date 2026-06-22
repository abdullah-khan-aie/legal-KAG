"""Reference / stub implementations of the outbound ports.

These make the pipeline runnable for a demo without standing up Neo4j, an
LLM, or an embedding service. Each class is a drop-in seam: replace it with a
real adapter (httpx fetcher, OpenAI embedder, Neo4j writer) one at a time.
"""

from __future__ import annotations

import logging
import re

from lodestone.domain.models.document import (
    Chunk,
    Entity,
    RawDocument,
    SourceRef,
    Triple,
)

logger = logging.getLogger(__name__)


class HttpDocumentSource:
    """Outbound: fetch document text from a URL, in memory only.

    Real impl: use httpx to GET the (signed) URL and extract text. We never
    persist the binary — legal requirement.
    """

    async def fetch(self, source: SourceRef) -> RawDocument:
        # TODO: replace with `async with httpx.AsyncClient() as c: ...`
        logger.debug("[stub] fetching %s", source.url)
        sample = (
            "Acme Corp entered into a service agreement with Globex on "
            "2024-03-01. The agreement is governed by the laws of Delaware."
        )
        return RawDocument(source=source, text=sample)


class SlidingWindowChunker:
    """Outbound: naive sentence-window splitter. Swap for semantic chunking."""

    def __init__(self, max_chars: int = 800, overlap: int = 100) -> None:
        self._max_chars = max_chars
        self._overlap = overlap

    def split(self, document: RawDocument) -> list[Chunk]:
        text = document.text.strip()
        chunks: list[Chunk] = []
        start = 0
        ordinal = 0
        while start < len(text):
            end = min(start + self._max_chars, len(text))
            chunks.append(Chunk(text=text[start:end], source=document.source, ordinal=ordinal))
            ordinal += 1
            start = end - self._overlap if end < len(text) else end
        logger.debug("[stub] split into %d chunks", len(chunks))
        return chunks


class RegexEntityExtractor:
    """Outbound: placeholder for the LLM extractor.

    Real impl: prompt an LLM (or KAG's SchemaFreeExtractor) for entities and
    SPO triples. Here we fake a couple so the graph write path is exercised.
    """

    _CAP = re.compile(r"\b([A-Z][a-z]+(?: [A-Z][a-z]+)?)\b")

    async def extract(self, chunk: Chunk) -> tuple[list[Entity], list[Triple]]:
        names = sorted(set(self._CAP.findall(chunk.text)))
        entities = [Entity(name=n, type="Unknown", chunk_id=chunk.chunk_id) for n in names]
        triples: list[Triple] = []
        if len(names) >= 2:
            triples.append(
                Triple(
                    subject=names[0],
                    predicate="related_to",
                    object=names[1],
                    chunk_id=chunk.chunk_id,
                )
            )
        return entities, triples


class FakeEmbedder:
    """Outbound: placeholder for the embedding model.

    Real impl: call OpenAI / bge-m3 / SiliconFlow and attach the vectors.
    """

    def __init__(self, dim: int = 8) -> None:
        self._dim = dim

    async def embed(self, chunks: list[Chunk]) -> list[Chunk]:
        out: list[Chunk] = []
        for c in chunks:
            vec = [float((hash(c.text) >> i) & 1) for i in range(self._dim)]
            out.append(
                Chunk(
                    text=c.text,
                    source=c.source,
                    ordinal=c.ordinal,
                    chunk_id=c.chunk_id,
                    embedding=vec,
                )
            )
        return out


class InMemoryKnowledgeGraph:
    """Outbound: stand-in for Neo4j / OpenSPG. Stores everything in dicts.

    Real impl: write chunks (text + vector index) and graph (entities,
    triples) into Neo4j. Chunk IDs link the vector and graph sides.
    """

    def __init__(self) -> None:
        self.chunks: dict[str, Chunk] = {}
        self.entities: list[Entity] = []
        self.triples: list[Triple] = []

    async def write_chunks(self, chunks: list[Chunk]) -> None:
        for c in chunks:
            self.chunks[c.chunk_id] = c
        logger.debug("[stub] wrote %d chunks (total %d)", len(chunks), len(self.chunks))

    async def write_graph(self, entities: list[Entity], triples: list[Triple]) -> None:
        self.entities.extend(entities)
        self.triples.extend(triples)
        logger.debug("[stub] wrote %d entities, %d triples", len(entities), len(triples))
