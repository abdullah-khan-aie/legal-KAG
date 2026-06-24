import logging
import traceback

from kag_extracted.builder.model.chunk import Chunk, ChunkTypeEnum
from kag_extracted.builder.model.sub_graph import SubGraph
from kag_extracted.common import Input, Output
from kag_extracted.interface import ExtractorABC, LLMClient, PromptABC
from kag_extracted.schema.client import CHUNK_TYPE, TABLE_TYPE
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


@ExtractorABC.register("atomic_query")
@ExtractorABC.register("atomic_query_extractor")
class AtomicQueryExtractor(ExtractorABC):
    def __init__(
        self,
        llm: LLMClient,
        prompt: PromptABC,
    ):
        super().__init__()
        self.llm = llm
        self.prompt = prompt

    @property
    def input_types(self) -> type[Input]:
        return Chunk

    @property
    def output_types(self) -> type[Output]:
        return SubGraph

    @staticmethod
    def output_indices() -> list[str]:
        return ["atomic_query_index"]

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=10, max=60),
        reraise=True,
    )
    async def aextract(self, passage: str):
        """
        Performs named entity recognition on a given text passage.
        Args:
            passage (str): The text to perform named entity recognition on.
        Returns:
            The result of the named entity recognition operation.
        """
        atomic_queries = await self.llm.ainvoke(
            {"content": passage}, self.prompt, with_except=False
        )

        return atomic_queries

    def extract(self, passage: str):
        """
        Performs named entity recognition on a given text passage.
        Args:
            passage (str): The text to perform named entity recognition on.
        Returns:
            The result of the named entity recognition operation.
        """
        atomic_queries = self.llm.invoke({"content": passage}, self.prompt, with_except=False)

        return atomic_queries

    async def _ainvoke(self, input: Chunk, **kwargs) -> list[SubGraph]:
        """
        Invokes the semantic extractor to process input data.

        Args:
            input (Input): Input data containing name and content.
            **kwargs: Additional keyword arguments.

        Returns:
            List[Output]: A list of processed results, containing subgraph information.
        """
        if input.type == ChunkTypeEnum.Text:
            o_label = CHUNK_TYPE
        else:
            o_label = TABLE_TYPE
        title = input.name
        passage = title + "\n" + input.content
        try:
            atomic_queries = await self.aextract(passage)
        except:  # noqa: E722
            print(f"Failed to extract atomic queries, info:\n{traceback.format_exc()}")
            atomic_queries = []
        subgraph = SubGraph([], [])
        chunk = input

        for atomic_query in atomic_queries:
            atomic_id = f"{chunk.id}_{atomic_query}"

            subgraph.add_node(
                id=atomic_id,
                name=atomic_query,
                label="AtomicQuery",
                properties={"name": atomic_query},
            )

            subgraph.add_edge(
                s_id=atomic_id,
                s_label="AtomicQuery",
                p="sourceChunk",
                o_id=f"{chunk.id}",
                o_label=o_label,
            )
        subgraph.id = chunk.id
        return [subgraph]

    def _invoke(self, input: Chunk, **kwargs) -> list[SubGraph]:
        """
        Invokes the semantic extractor to process input data.

        Args:
            input (Input): Input data containing name and content.
            **kwargs: Additional keyword arguments.

        Returns:
            List[Output]: A list of processed results, containing subgraph information.
        """
        if input.type == ChunkTypeEnum.Text:
            o_label = CHUNK_TYPE
        else:
            o_label = TABLE_TYPE
        title = input.name
        passage = title + "\n" + input.content
        try:
            atomic_queries = self.extract(passage)
        except:  # noqa: E722
            print(f"Failed to extract atomic queries, info:\n{traceback.format_exc()}")
            atomic_queries = []
        subgraph = SubGraph([], [])
        chunk = input

        for atomic_query in atomic_queries:
            atomic_id = f"{chunk.id}_{atomic_query}"

            subgraph.add_node(
                id=atomic_id,
                name=atomic_query,
                label="AtomicQuery",
                properties={"name": atomic_query},
            )

            subgraph.add_edge(
                s_id=atomic_id,
                s_label="AtomicQuery",
                p="sourceChunk",
                o_id=f"{chunk.id}",
                o_label=o_label,
            )
        subgraph.id = chunk.id
        return [subgraph]
