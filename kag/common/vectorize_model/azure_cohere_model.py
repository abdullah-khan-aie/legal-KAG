# Azure-hosted Cohere embeddings via the Azure AI Inference SDK (async-capable).
#
# Mirrors kag's AzureOpenAIVectorizeModel structure (same VectorizeModelABC base,
# vectorize/avectorize, generate_key, rate-limited async) but targets a Cohere
# serverless / managed deployment on Azure AI Foundry through azure-ai-inference,
# instead of Azure OpenAI through the openai SDK.
#
# Cohere embeddings are input-type aware: ingestion uses "document", query-time
# retrieval uses "query". NOTE: passing input_type to Cohere through
# azure-ai-inference is version-sensitive (it is often only honored via
# `model_extras`). Defaults to the model_extras path; set input_type_via_extras=
# False if your deployment honors the plain `input_type` parameter.

from collections.abc import Iterable

from azure.ai.inference import EmbeddingsClient
from azure.ai.inference.aio import EmbeddingsClient as AsyncEmbeddingsClient
from azure.core.credentials import AzureKeyCredential

from kag.interface.common.vectorize_model import EmbeddingVector, VectorizeModelABC


@VectorizeModelABC.register("azure_cohere")
class AzureCohereVectorizeModel(VectorizeModelABC):
    """``VectorizeModelABC`` backed by an Azure-hosted Cohere embedding endpoint."""

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        model: str = None,
        input_type: str = "document",
        input_type_via_extras: bool = True,
        vector_dimensions: int = None,
        max_rate: float = 1000,
        time_period: float = 1,
    ):
        """
        Args:
            endpoint: The Azure AI Foundry serverless/managed Cohere endpoint URL.
            api_key: The key for the endpoint.
            model: Optional model/deployment name (omit for single-model endpoints).
            input_type: Cohere input type for this model instance ("document" for
                ingestion, "query" for retrieval).
            input_type_via_extras: Pass input_type through model_extras (reliable on
                azure-ai-inference for Cohere) vs the plain `input_type` parameter.
            vector_dimensions: Optional embedding dimensionality (for Matryoshka models).
        """
        name = self.generate_key(endpoint, api_key, model)
        super().__init__(name, vector_dimensions, max_rate, time_period)
        self.model = model
        self.input_type = input_type
        self.input_type_via_extras = input_type_via_extras
        cred = AzureKeyCredential(api_key)
        self.client = EmbeddingsClient(endpoint=endpoint, credential=cred)
        self.aclient = AsyncEmbeddingsClient(endpoint=endpoint, credential=cred)

    @classmethod
    def generate_key(cls, endpoint, api_key, model, *args, **kwargs) -> str:
        return f"{cls}_{endpoint}_{api_key}_{model}"

    def _embed_kwargs(self, payload: list[str]) -> dict:
        kwargs = {"input": payload}
        if self.model:
            kwargs["model"] = self.model
        if self.input_type:
            if self.input_type_via_extras:
                kwargs["model_extras"] = {"input_type": self.input_type}
            else:
                kwargs["input_type"] = self.input_type
        return kwargs

    def vectorize(self, texts: str | Iterable[str]) -> EmbeddingVector | Iterable[EmbeddingVector]:
        single = isinstance(texts, str)
        payload = [texts] if single else list(texts)
        response = self.client.embed(**self._embed_kwargs(payload))
        results = [item.embedding for item in response.data]
        if single:
            assert len(results) == 1
            return results[0]
        assert len(results) == len(payload)
        return results

    async def avectorize(
        self, texts: str | Iterable[str]
    ) -> EmbeddingVector | Iterable[EmbeddingVector]:
        single = isinstance(texts, str)
        payload = [texts] if single else list(texts)
        async with self.limiter:
            response = await self.aclient.embed(**self._embed_kwargs(payload))
        results = [item.embedding for item in response.data]
        if single:
            assert len(results) == 1
            return results[0]
        assert len(results) == len(payload)
        return results
