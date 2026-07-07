# Cohere Embed on Amazon Bedrock (bedrock-runtime InvokeModel).
#
# Sync ``vectorize`` uses boto3; async ``avectorize`` uses aioboto3 (native async
# I/O) so batches of embeddings run concurrently without a thread bridge.
#
# Cohere is input-type aware: ingestion embeds the corpus with "search_document"
# and retrieval embeds queries with "search_query". We accept kag's "document"/
# "query" aliases too and normalize them.

import asyncio
import json
from collections.abc import Iterable

import aioboto3
import boto3
from botocore.config import Config
from tenacity import retry, stop_after_attempt

from kag.interface.common.vectorize_model import EmbeddingVector, VectorizeModelABC

# Normalize kag-style input types to Cohere's Bedrock vocabulary.
_INPUT_TYPE_ALIASES = {
    "document": "search_document",
    "query": "search_query",
}


def _unwrap_secret(value):
    """Return the plaintext of a SecretStr, or the value unchanged."""
    return value.get_secret_value() if hasattr(value, "get_secret_value") else value


@VectorizeModelABC.register("bedrock_cohere")
class BedrockCohereVectorizeModel(VectorizeModelABC):
    """``VectorizeModelABC`` backed by Cohere Embed on Amazon Bedrock."""

    def __init__(
        self,
        region: str,
        model: str = "cohere.embed-v4:0",
        input_type: str = "search_document",
        output_dimension: int = None,
        vector_dimensions: int = None,
        max_rate: float = 1000,
        time_period: float = 1,
        **kwargs,
    ):
        """Initialize the Bedrock Cohere embedding client.

        Args:
            region: AWS region hosting the Bedrock endpoint (e.g. "us-west-2").
            model: Bedrock Cohere Embed model id (default "cohere.embed-v4:0").
            input_type: "search_document" for ingest, "search_query" for
                retrieval ("document"/"query" aliases are accepted).
            output_dimension: Optional embedding length (256/512/1024/1536).
            vector_dimensions: Optional pre-declared dimensionality.

        Optional ``aws_access_key_id`` / ``aws_secret_access_key`` (str or
        SecretStr, via kwargs) use those credentials explicitly; passing them as
        kwargs keeps a SecretStr unstringified through the registry and masked in
        logs. With none, auth falls back to boto3's standard credential chain.
        """
        aws_access_key_id = _unwrap_secret(kwargs.pop("aws_access_key_id", None))
        aws_secret_access_key = _unwrap_secret(kwargs.pop("aws_secret_access_key", None))
        name = self.generate_key(region, model, input_type)
        super().__init__(name, vector_dimensions, max_rate, time_period)
        self.region = region
        self.model = model
        self.input_type = _INPUT_TYPE_ALIASES.get(input_type, input_type)
        self.output_dimension = output_dimension
        # Explicit Bedrock credentials (when supplied) take precedence over the
        # environment/instance-role chain.
        self._credentials = {}
        if aws_access_key_id and aws_secret_access_key:
            self._credentials = {
                "aws_access_key_id": aws_access_key_id,
                "aws_secret_access_key": aws_secret_access_key,
            }
        # Adaptive retry backs off on ThrottlingException; raise the connection
        # pool well above boto3's default of 10 so it never caps in-flight embeds.
        self._config = Config(
            retries={"mode": "adaptive", "total_max_attempts": 10},
            max_pool_connections=256,
        )
        # Sync client for the blocking ``vectorize`` path; async client (aioboto3)
        # for ``avectorize``, created lazily on first use and reused.
        self.client = boto3.client(
            "bedrock-runtime", region_name=region, config=self._config, **self._credentials
        )
        self._session = aioboto3.Session(**self._credentials)
        self._aclient = None
        self._aclient_cm = None
        self._aclient_lock = asyncio.Lock()

    @classmethod
    def generate_key(cls, region, model, input_type, *args, **kwargs) -> str:
        return f"{cls}_{region}_{model}_{input_type}"

    @staticmethod
    def _extract_float_vectors(body: dict) -> list:
        """Pull float vectors out of a Cohere Embed response.

        The response ``embeddings`` field is a plain list of vectors when a
        single embedding type is returned, or a dict keyed by type (e.g.
        ``{"float": [...]}``) otherwise. Handle both defensively.
        """
        embeddings = body["embeddings"]
        if isinstance(embeddings, dict):
            return embeddings.get("float") or next(iter(embeddings.values()))
        return embeddings

    def vectorize(self, texts: str | Iterable[str]) -> EmbeddingVector | Iterable[EmbeddingVector]:
        single = isinstance(texts, str)
        payload = [texts] if single else list(texts)

        request: dict = {
            "texts": payload,
            "input_type": self.input_type,
            "embedding_types": ["float"],
        }
        if self.output_dimension:
            request["output_dimension"] = self.output_dimension

        response = self.client.invoke_model(
            modelId=self.model,
            body=json.dumps(request),
            accept="*/*",
            contentType="application/json",
        )
        body = json.loads(response["body"].read())
        results = self._extract_float_vectors(body)

        if single:
            assert len(results) == 1
            return results[0]
        assert len(results) == len(payload)
        return results

    async def _aget_client(self):
        """Return the shared aioboto3 client, created lazily on the running loop."""
        if self._aclient is None:
            async with self._aclient_lock:
                if self._aclient is None:
                    self._aclient_cm = self._session.client(
                        "bedrock-runtime", region_name=self.region, config=self._config
                    )
                    self._aclient = await self._aclient_cm.__aenter__()
        return self._aclient

    @retry(stop=stop_after_attempt(3), reraise=True)
    async def avectorize(
        self, texts: str | Iterable[str]
    ) -> EmbeddingVector | Iterable[EmbeddingVector]:
        """Async embedding over aioboto3 (no rate limiter; concurrency-bounded)."""
        return await self._avectorize(texts)

    async def _avectorize(
        self, texts: str | Iterable[str]
    ) -> EmbeddingVector | Iterable[EmbeddingVector]:
        single = isinstance(texts, str)
        payload = [texts] if single else list(texts)

        request: dict = {
            "texts": payload,
            "input_type": self.input_type,
            "embedding_types": ["float"],
        }
        if self.output_dimension:
            request["output_dimension"] = self.output_dimension

        client = await self._aget_client()
        response = await client.invoke_model(
            modelId=self.model,
            body=json.dumps(request),
            accept="*/*",
            contentType="application/json",
        )
        body = json.loads(await response["body"].read())
        results = self._extract_float_vectors(body)

        if single:
            assert len(results) == 1
            return results[0]
        assert len(results) == len(payload)
        return results
