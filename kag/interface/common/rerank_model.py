import asyncio
import io
import logging
import os
import tarfile

import numpy as np
import requests

from kag.common.rate_limiter import RATE_LIMITER_MANGER
from kag.common.registry import Registrable

logger = logging.getLogger()


@Registrable.register("rerank_model")
class RerankModelABC(Registrable):
    """Abstract base class for reranking models with rate limiting capabilities.

    Provides core functionality for model downloading and reranking operations,
    including rate limiting and error handling for index computation.

    Args:
        name: Identifier for the rate limiter.
        max_rate: Maximum allowed requests per time period.
        time_period: Time window for rate limiting, in seconds.
    """

    def __init__(
        self,
        name: str,
        max_rate: float = 1000,
        time_period: float = 1,
    ):
        self.limiter = RATE_LIMITER_MANGER.get_rate_limiter(name, max_rate, time_period)

    def _download_model(self, path, url):
        """Download and extract a model archive from the specified URL.

        Verifies the presence of a valid config.json file in the extracted contents.

        Args:
            path: Destination directory for extraction.
            url: Source URL of the model archive.

        Raises:
            RuntimeError: If config.json is missing from the extracted contents.
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

    def compute_index(self, query: str, passages: list[str]):
        """Compute reranked passage indices for a query.

        Must be implemented by subclasses to provide the actual reranking logic.

        Args:
            query: Search query string.
            passages: Document passages to rerank.

        Returns:
            Passage indices in descending order of relevance.

        Raises:
            NotImplementedError: If not overridden by subclasses.
        """
        message = "abstract method compute_index is not implemented"
        raise NotImplementedError(message)

    def rerank(self, queries: list[str], passages: list[str]):
        """Rerank passages across multiple queries with error recovery.

        Combines reranking results from multiple queries using reciprocal rank fusion,
        falling back to the original ranking if compute_index fails.

        Args:
            queries: Query strings to rerank against.
            passages: Passages to rerank.

        Returns:
            Passages in descending order of combined scores.
        """
        rank_scores = np.array([1 / (1 + i) for i in range(len(passages))])
        passage_scores = np.zeros(len(passages)) + rank_scores
        for query in queries:
            try:
                sorted_idx = self.compute_index(query, passages)
            except Exception as e:
                import traceback

                traceback.print_exc()
                logger.warning(
                    f"failed to compute reranked index, fallback to origin rank, info: {e}"
                )
                sorted_idx = list(range(len(passages)))
            for rank, passage_id in enumerate(sorted_idx):
                passage_scores[passage_id] += rank_scores[rank]

        merged_sorted_idx = np.argsort(-passage_scores)
        new_passages = [passages[x] for x in merged_sorted_idx]
        return new_passages

    async def arerank(self, queries: list[str], passages: list[str]):
        """Asynchronously rerank passages with rate limiting.

        Applies rate limiting and runs the synchronous rerank call in a thread.

        Args:
            queries: Query strings to rerank against.
            passages: Passages to rerank.

        Returns:
            Passages in descending order of combined scores.
        """
        async with self.limiter:
            return await asyncio.to_thread(lambda: self.rerank(queries, passages))
