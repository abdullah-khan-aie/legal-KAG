# Cohere Embed on Amazon Bedrock via boto3 (bedrock-runtime InvokeModel).
#
# Mirrors kag's VectorizeModelABC contract (generate_key, sync vectorize) but
# targets Cohere Embed v4 on Bedrock instead of an Azure-hosted endpoint. Only
# the sync ``vectorize`` is implemented -- the base class's ``avectorize`` wraps
# it in a rate-limited ``asyncio.to_thread`` call, which is the right shape for
# boto3's synchronous client.
#
# Cohere is input-type aware: ingestion embeds the corpus with "search_document"
# and retrieval embeds queries with "search_query". We accept kag's "document"/
# "query" aliases too and normalize them.

import json
from collections.abc import Iterable

import boto3
from botocore.config import Config

from kag.interface.common.vectorize_model import EmbeddingVector, VectorizeModelABC

# Normalize kag-style input types to Cohere's Bedrock vocabulary.
_INPUT_TYPE_ALIASES = {
    "document": "search_document",
    "query": "search_query",
}


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
    ):
        """Initialize the Bedrock Cohere embedding client.

        Args:
            region: AWS region hosting the Bedrock endpoint (e.g. "us-west-2").
            model: Bedrock Cohere Embed model id (default "cohere.embed-v4:0").
            input_type: "search_document" for ingest, "search_query" for
                retrieval ("document"/"query" aliases are accepted).
            output_dimension: Optional embedding length (256/512/1024/1536).
            vector_dimensions: Optional pre-declared dimensionality.

        Auth: boto3 uses the standard AWS credential chain (SSO profile via
        ``aws sso login``, environment credentials, or an instance role).
        """
        name = self.generate_key(region, model, input_type)
        super().__init__(name, vector_dimensions, max_rate, time_period)
        self.region = region
        self.model = model
        self.input_type = _INPUT_TYPE_ALIASES.get(input_type, input_type)
        self.output_dimension = output_dimension
        # Adaptive retries ride out Bedrock throttling (client-side rate-limiting
        # + exponential backoff) while the account's per-minute quota is low.
        self.client = boto3.client(
            "bedrock-runtime",
            region_name=region,
            config=Config(retries={"max_attempts": 10, "mode": "adaptive"}),
        )

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

    def vectorize(
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
