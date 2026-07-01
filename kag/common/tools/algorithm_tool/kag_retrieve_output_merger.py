import math

from kag.interface import (
    ChunkData,
    KgGraph,
    RetrieverOutput,
    RetrieverOutputMerger,
    Task,
)


@RetrieverOutputMerger.register("kag_merger")
class KAGRetrieverOutputMerger(RetrieverOutputMerger):
    """Merge retrieved chunks from multiple retrievers into a unified result.

    Attributes:
        name: Identifier for the merger instance.
        merge_method: Method used for merging results ("rrf" or "weightd").
        score_normalizer: Normalization function selected from merge_method.
    """

    def __init__(
        self,
        merge_method: str = "rrf",
        **kwargs,
    ):
        """Initialize the merger with the given normalization strategy.

        Args:
            merge_method: Score normalization method ("rrf" for reciprocal rank fusion
                or "weightd" for min-max normalization). Defaults to "rrf".
            **kwargs: Additional keyword arguments for base class initialization.
        """
        super().__init__(**kwargs)
        self.merge_method = merge_method
        if self.merge_method.lower().strip() == "weightd":
            self.score_normalizer = self.min_max_normalize
        else:
            self.score_normalizer = self.rrf_normalize

    @staticmethod
    def min_max_normalize(chunks: list[ChunkData]):
        """Normalize chunk scores in-place using min-max scaling.

        Args:
            chunks: Chunks whose score attributes are updated in-place.
        """
        if len(chunks) == 0:
            return []
        scores = [x.score for x in chunks]
        max_score = max(scores)
        min_score = min(scores)
        for chunk in chunks:
            score = chunk.score
            if math.isclose(max_score, min_score, rel_tol=1e-9):
                score = 1
            else:
                score = (score - min_score) / (max_score - min_score)
            chunk.score = score
        return None

    @staticmethod
    def rrf_normalize(chunks: list[ChunkData]):
        """Normalize scores in-place using reciprocal rank fusion (RRF).

        Args:
            chunks: Chunks whose score attributes are updated in-place.
        """
        if len(chunks) == 0:
            return []
        for idx, chunk in enumerate(chunks):
            score = 1 / (idx + 1)
            chunk.score = score
        return None

    @staticmethod
    def chunk_merge(chunk_lists: list[list[ChunkData]], score_normalizer):
        """Merge multiple chunk lists into a unified ranked list.

        Args:
            chunk_lists: Chunk lists from different retrievers.
            score_normalizer: Normalization function to apply before merging.

        Returns:
            Merged chunks sorted by aggregated score, highest first.
        """
        merged = {}
        chunk_map = {}
        for chunks in chunk_lists:
            score_normalizer(chunks)
            for chunk in chunks:
                chunk_id = chunk.chunk_id
                if chunk_id in merged:
                    merged[chunk_id] += chunk.score
                else:
                    merged[chunk_id] = chunk.score
                if chunk_id not in chunk_map:
                    chunk_map[chunk_id] = chunk
        sorted_chunk_ids = sorted(merged.items(), key=lambda x: -x[1])
        output = []
        for item in sorted_chunk_ids:
            chunk_id, score = item
            chunk = chunk_map[chunk_id]
            output.append(
                ChunkData(
                    content=chunk.content,
                    title=chunk.title,
                    chunk_id=chunk.chunk_id,
                    score=score,
                )
            )

        return output

    def invoke(
        self, task: Task, retrieve_outputs: list[RetrieverOutput], **kwargs
    ) -> RetrieverOutput:
        """Merge retriever outputs into a single unified output.

        Args:
            task: Current processing task containing context information.
            retrieve_outputs: Outputs from the different retrievers to merge.
            **kwargs: Additional keyword arguments; may include ``retrieved_chunks``
                to extend with the merged chunk contents.

        Returns:
            Merged output containing the unified chunk list and graph.
        """
        retrieved_chunks = kwargs.get("retrieved_chunks", None)
        chunk_lists = [x.chunks for x in retrieve_outputs]
        merged = self.chunk_merge(chunk_lists, self.rrf_normalize)
        if retrieved_chunks is not None:
            chunk_texts = [x.content for x in merged]
            retrieved_chunks.extend(chunk_texts)
        graph = KgGraph()
        for x in retrieve_outputs:
            for g in x.graphs:
                graph.merge_kg_graph(g)
        return RetrieverOutput(
            retriever_method=self.name,
            chunks=merged,
            graphs=[graph],
        )

    def schema(self):
        return {"name": "kag_merger"}
