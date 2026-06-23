"""Driven (outbound) ports the ingestion pipeline depends on.

These are the only EXTERNAL resources the current pipeline consumes (no API,
no graph store yet). Defined by intent, not by technology — an adapter binds a
concrete model (OpenAI/DeepSeek/Ollama/...) without the core knowing which.
"""

from __future__ import annotations

from typing import Protocol


class LanguageModelPort(Protocol):
    """A chat/completion model. Consumed by the extractor (NER/std/triple) and,
    if used, the semantic splitter. Given a rendered prompt, return the reply."""

    def complete(self, prompt: str, **kwargs) -> str: ...


class EmbeddingModelPort(Protocol):
    """A text-embedding model. Consumed by the vectorizer.
    Maps a batch of texts to their vectors."""

    def embed(self, texts: list[str]) -> list[list[float]]: ...
