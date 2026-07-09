# Cohere Embed via Cohere's official API (direct, not Amazon Bedrock).
#
# Async ``avectorize`` uses ``cohere.AsyncClientV2`` (native async I/O, no thread
# bridge) -- this is the path ingestion drives through BatchVectorizer.ainvoke.
# Sync ``vectorize`` uses ``cohere.ClientV2`` and is created lazily, only if a
# blocking caller actually hits it (entity linking during post-processing, and
# the query-time vector retrievers, which call the sync method). An async client
# is bound to the event loop it runs on, so a sync caller cannot share it; the
# lazy sync client mirrors the sync/async split of the Anthropic LLM client, for
# the same reason -- but it is never constructed in a pure-async path.
#
# Cohere is input-type aware: ingestion embeds the corpus with "search_document"
# and retrieval embeds queries with "search_query". We accept kag's "document"/
# "query" aliases too and normalize them.

import asyncio
import contextlib
from collections.abc import Iterable

import cohere
from tenacity import retry, stop_after_attempt

from kag.interface.common.vectorize_model import EmbeddingVector, VectorizeModelABC

# Normalize kag-style input types to Cohere's vocabulary.
_INPUT_TYPE_ALIASES = {
    "document": "search_document",
    "query": "search_query",
}


def _obs():
    """Lazily import the app's observability helpers (kag stays standalone)."""
    try:
        from src.lodestone.observability import tracing as o

        return o
    except Exception:
        return None


def _billed_tokens(response):
    """Best-effort read of Cohere's billed input tokens; None if unavailable."""
    try:
        return response.meta.billed_units.input_tokens
    except Exception:
        return None


def _unwrap_secret(value):
    """Return the plaintext of a SecretStr, or the value unchanged."""
    return value.get_secret_value() if hasattr(value, "get_secret_value") else value


@VectorizeModelABC.register("cohere")
class CohereVectorizeModel(VectorizeModelABC):
    """``VectorizeModelABC`` backed by Cohere Embed via Cohere's own API."""

    def __init__(
        self,
        model: str = "embed-v4.0",
        input_type: str = "search_document",
        output_dimension: int | None = None,
        vector_dimensions: int | None = None,
        **kwargs,
    ):
        """Initialize the direct Cohere embedding client.

        Args:
            model: Cohere Embed model id (default "embed-v4.0").
            input_type: "search_document" for ingest, "search_query" for
                retrieval ("document"/"query" aliases are accepted).
            output_dimension: Embedding length (256/512/1024/1536 for embed-v4).
            vector_dimensions: Pre-declared dimensionality; defaults to
                ``output_dimension`` so ``get_vector_dimensions`` never needs a
                probe call.

        The Cohere API key is passed via ``api_key`` (str or SecretStr, through
        kwargs) -- passing it as a kwarg keeps a SecretStr unstringified through
        the registry and masked in logs, and it is unwrapped only here. With no
        key, the SDK falls back to the ``CO_API_KEY`` environment variable.
        """
        api_key = _unwrap_secret(kwargs.pop("api_key", None))
        name = self.generate_key(model, input_type)
        super().__init__(name, vector_dimensions or output_dimension)
        self.model = model
        self.input_type = _INPUT_TYPE_ALIASES.get(input_type, input_type)
        self.output_dimension = output_dimension
        self._api_key = api_key
        # One async client, reused across the server's event loop; the sync
        # client is created lazily and only if a blocking caller needs it.
        self._aclient: cohere.AsyncClientV2 | None = None
        self._client: cohere.ClientV2 | None = None
        self._aclient_lock = asyncio.Lock()

    @classmethod
    def generate_key(cls, model, input_type, *args, **kwargs) -> str:
        return f"{cls}_{model}_{input_type}"

    def _request(self, payload: list[str]) -> dict:
        """Build the embed request body shared by the sync and async paths."""
        request: dict = {
            "model": self.model,
            "texts": payload,
            "input_type": self.input_type,
            "embedding_types": ["float"],
        }
        if self.output_dimension:
            request["output_dimension"] = self.output_dimension
        return request

    @staticmethod
    def _floats(response) -> list:
        """Pull the float vectors out of an embed response.

        The v2 response exposes them on ``embeddings.float_`` (the SDK renames the
        JSON ``float`` field, since ``float`` is a Python builtin).
        """
        return response.embeddings.float_

    @retry(stop=stop_after_attempt(3), reraise=True)
    def vectorize(self, texts: str | Iterable[str]) -> EmbeddingVector | Iterable[EmbeddingVector]:
        """Blocking embedding via ``cohere.ClientV2`` (lazily constructed)."""
        single = isinstance(texts, str)
        payload = [texts] if single else list(texts)

        if self._client is None:
            self._client = cohere.ClientV2(api_key=self._api_key)
        response = self._client.embed(**self._request(payload))
        results = self._floats(response)

        if single:
            assert len(results) == 1
            return results[0]
        assert len(results) == len(payload)
        return results

    async def _aget_client(self) -> cohere.AsyncClientV2:
        """Return the shared async client, created lazily on the running loop."""
        if self._aclient is None:
            async with self._aclient_lock:
                if self._aclient is None:
                    self._aclient = cohere.AsyncClientV2(api_key=self._api_key)
        return self._aclient

    @retry(stop=stop_after_attempt(3), reraise=True)
    async def avectorize(
        self, texts: str | Iterable[str]
    ) -> EmbeddingVector | Iterable[EmbeddingVector]:
        """Native async embedding via ``cohere.AsyncClientV2`` (no thread bridge)."""
        single = isinstance(texts, str)
        payload = [texts] if single else list(texts)

        client = await self._aget_client()
        # Trace as a Langfuse generation (nested under the document's "embed"
        # span) with Cohere token usage where available, else the text count.
        o = _obs()
        gen_cm = o.span("cohere.embed", as_type="generation", model=self.model) if o else None
        with gen_cm if gen_cm is not None else contextlib.nullcontext() as gen:
            response = await client.embed(**self._request(payload))
            if o is not None and gen is not None:
                toks = _billed_tokens(response)
                o.record_generation_usage(
                    gen,
                    model=self.model,
                    input_tokens=toks if toks is not None else len(payload),
                    kind="embed",
                )
        results = self._floats(response)

        if single:
            assert len(results) == 1
            return results[0]
        assert len(results) == len(payload)
        return results
