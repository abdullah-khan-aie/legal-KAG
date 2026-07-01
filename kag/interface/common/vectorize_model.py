import asyncio
import io
import logging
import os
import tarfile
import threading
from collections.abc import Iterable, Mapping
from typing import ClassVar

import requests
from tenacity import retry, stop_after_attempt

from kag.common.rate_limiter import RATE_LIMITER_MANGER
from kag.common.registry import Registrable

EmbeddingVector = Iterable[float]
SparseEmbeddingVector = Mapping[str, float] | str
logger = logging.getLogger()


@Registrable.register("vectorize_model")
class VectorizeModelABC(Registrable):
    """Abstract base class defining the interface for converting text into embedding vectors."""

    _instances: ClassVar[dict] = {}
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        key = cls.generate_key(*args, **kwargs)

        if key in cls._instances:
            return cls._instances[key]

        instance = super().__new__(cls)
        cls._instances[key] = instance
        return instance

    def __init__(
        self,
        name: str,
        vector_dimensions: int = None,
        max_rate: float = 1000,
        time_period: float = 1,
    ):
        """Initialize the vectorize model.

        Args:
            name: Identifier used for the shared rate limiter.
            vector_dimensions: Number of dimensions for the embedding vectors.
            max_rate: Maximum allowed requests per time period.
            time_period: Time window for rate limiting, in seconds.
        """
        super().__init__()
        self._vector_dimensions = vector_dimensions
        self.limiter = RATE_LIMITER_MANGER.get_rate_limiter(name, max_rate, time_period)

    def _download_model(self, path, url):
        """Download a model archive from the given URL and extract it to a path.

        Args:
            path: Directory to extract the downloaded model into.
            url: URL of the model archive.

        Raises:
            RuntimeError: If the model configuration file is missing after extraction.
        """
        logger.info(f"download model from:\n{url} to:\n{path}")
        res = requests.get(url)
        with io.BytesIO(res.content) as fileobj:
            with tarfile.open(fileobj=fileobj) as tar:
                tar.extractall(path=path)
        config_path = os.path.join(path, "config.json")
        if not os.path.isfile(config_path):
            message = (
                f"model config not found at {config_path!r}, url {url!r} specified an invalid model"
            )
            raise RuntimeError(message)

    def get_vector_dimensions(self):
        """Return the dimension of the generated embedding vectors.

        Raises:
            RuntimeError: If the embedding service is not available.
        """
        if hasattr(self, "_vector_dimensions"):
            return int(self._vector_dimensions)
        try:
            example_input = "This is a test."
            example_vector = self.vectorize(example_input)
            self._vector_dimensions = len(example_vector)
            return self._vector_dimensions

        except Exception as ex:
            message = "the embedding service is not available"
            raise RuntimeError(message) from ex

    @classmethod
    def generate_key(cls, *args, **kwargs) -> str:
        return f"{cls}"

    @retry(stop=stop_after_attempt(3), reraise=True)
    def vectorize(self, texts: str | Iterable[str]) -> EmbeddingVector | Iterable[EmbeddingVector]:
        """Vectorize one or more texts into embedding vectors.

        Args:
            texts: A single text or an iterable of texts to vectorize.

        Returns:
            The embedding vector(s) for the input text(s).

        Raises:
            NotImplementedError: This method must be implemented by subclasses.
        """
        message = "abstract method vectorize is not implemented"
        raise NotImplementedError(message)

    @retry(stop=stop_after_attempt(3), reraise=True)
    async def avectorize(
        self, texts: str | Iterable[str]
    ) -> EmbeddingVector | Iterable[EmbeddingVector]:
        """Asynchronously vectorize one or more texts into embedding vectors.

        Applies rate limiting and runs the synchronous vectorize call in a thread.

        Args:
            texts: A single text or an iterable of texts to vectorize.

        Returns:
            The embedding vector(s) for the input text(s).
        """

        async with self.limiter:
            return await asyncio.to_thread(lambda: self.vectorize(texts))


@Registrable.register("sparse_vectorize_model")
class SparseVectorizeModelABC(Registrable):
    """Abstract base class defining the interface for converting text into sparse embedding vectors."""

    _instances: ClassVar[dict] = {}
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        key = cls.generate_key(*args, **kwargs)

        if key in cls._instances:
            return cls._instances[key]

        instance = super().__new__(cls)
        cls._instances[key] = instance
        return instance

    def __init__(
        self,
        name: str,
        max_rate: float = 1000,
        time_period: float = 1,
    ):
        """Initialize the sparse vectorize model.

        Args:
            name: Identifier used for the shared rate limiter.
            max_rate: Maximum allowed requests per time period.
            time_period: Time window for rate limiting, in seconds.
        """
        super().__init__()
        self.limiter = RATE_LIMITER_MANGER.get_rate_limiter(name, max_rate, time_period)

    def _download_model(self, path, url):
        """Download a model archive from the given URL and extract it to a path.

        Args:
            path: Directory to extract the downloaded model into.
            url: URL of the model archive.

        Raises:
            RuntimeError: If the model configuration file is missing after extraction.
        """
        logger.info(f"download model from:\n{url} to:\n{path}")
        res = requests.get(url)
        with io.BytesIO(res.content) as fileobj:
            with tarfile.open(fileobj=fileobj) as tar:
                tar.extractall(path=path)
        config_path = os.path.join(path, "config.json")
        if not os.path.isfile(config_path):
            message = (
                f"model config not found at {config_path!r}, url {url!r} specified an invalid model"
            )
            raise RuntimeError(message)

    @classmethod
    def generate_key(cls, *args, **kwargs) -> str:
        return f"{cls}"

    @retry(stop=stop_after_attempt(3), reraise=True)
    def vectorize(
        self, texts: str | Iterable[str]
    ) -> SparseEmbeddingVector | Iterable[SparseEmbeddingVector]:
        """Vectorize one or more texts into sparse embedding vectors.

        Args:
            texts: A single text or an iterable of texts to vectorize.

        Returns:
            The sparse embedding vector(s) for the input text(s).

        Raises:
            NotImplementedError: This method must be implemented by subclasses.
        """
        message = "abstract method vectorize is not implemented"
        raise NotImplementedError(message)

    @retry(stop=stop_after_attempt(3), reraise=True)
    async def avectorize(
        self, texts: str | Iterable[str]
    ) -> SparseEmbeddingVector | Iterable[SparseEmbeddingVector]:
        """Asynchronously vectorize one or more texts into sparse embedding vectors.

        Applies rate limiting and runs the synchronous vectorize call in a thread.

        Args:
            texts: A single text or an iterable of texts to vectorize.

        Returns:
            The sparse embedding vector(s) for the input text(s).
        """

        async with self.limiter:
            return await asyncio.to_thread(lambda: self.vectorize(texts))
