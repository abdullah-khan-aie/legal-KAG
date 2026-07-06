import logging

from kag.builder.model.chunk import Chunk, ChunkTypeEnum
from kag.builder.model.sub_graph import SubGraph
from kag.common import Input, Output
from kag.interface import ExtractorABC, LLMClient, PromptABC
from kag.schema.client import CHUNK_TYPE, TABLE_TYPE

logger = logging.getLogger(__name__)


@ExtractorABC.register("summary_extractor")
class SummaryExtractor(ExtractorABC):
    def __init__(
        self,
        llm_module: LLMClient = None,
        chunk_summary_prompt: PromptABC = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.llm_module = llm_module
        from kag.builder.prompt.chunk_summary_prompt import ChunkSummaryPrompt

        self.chunk_summary_prompt = chunk_summary_prompt or ChunkSummaryPrompt()

    @property
    def input_types(self):
        return Chunk

    @property
    def output_types(self):
        return [SubGraph]

    @property
    def inherit_input_key(self):
        return True

    @staticmethod
    def output_indices() -> list[str]:
        return ["Summary"]

    def _invoke(self, data: Input, **kwargs) -> list[Output]:
        """Summarize the chunk via the LLM and build a Summary subgraph.

        Args:
            data: The chunk to summarize.
        """
        if data.type == ChunkTypeEnum.Text:
            o_label = CHUNK_TYPE
        else:
            o_label = TABLE_TYPE

        summary_name = data.name

        index = summary_name.find("_split")
        if index != -1:
            summary_name = summary_name[:index]

        content = data.content
        summary = self.llm_module.invoke(
            {"content": content}, self.chunk_summary_prompt, with_json_parse=False
        )

        sub_graph = SubGraph([], [])
        # add Summary Node
        sub_graph.add_node(
            id=data.id,
            name=summary_name,
            label="Summary",
            properties={
                "id": data.id,
                "name": summary_name,
                "content": summary,
            },
        )

        parent_id = getattr(data, "parent_id", None)
        if parent_id is not None:
            # add Summary_childOf_Summary edge
            sub_graph.add_edge(
                s_id=data.id,
                s_label="Summary",
                p="childOf",
                o_id=parent_id,
                o_label="Summary",
                properties={},
            )

        # add Summary_sourceChunk_Chunk edge
        sub_graph.add_edge(
            s_id=data.id,
            s_label="Summary",
            p="sourceChunk",
            o_id=f"{data.id}",
            o_label=o_label,
            properties={},
        )

        return [sub_graph]
