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

        return [self._build_summary_subgraph(data, summary_name, summary, o_label)]

    async def _ainvoke(self, data: Input, **kwargs) -> list[Output]:
        """Async twin of ``_invoke``: summarise the chunk on the async LLM path.

        Identical to ``_invoke`` except the LLM call goes through
        ``llm_module.ainvoke`` (the async ``self.limiter`` bucket) instead of the
        sync ``invoke`` (the separate ``sync_limiter`` bucket). This puts summary
        calls in the SAME process-global async rate limiter as the schema
        extractor's NER/SPO/event/std calls -- one shared bucket, one true global
        rate -- rather than a second independent bucket that would sum on top of
        it. It also keeps the call off the thread pool. ``ainvoke`` mirrors
        ``invoke`` line-for-line (same signature, same ``with_json_parse=False``
        branch, same ``parse_response``), so the summary output is unchanged.
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
        summary = await self.llm_module.ainvoke(
            {"content": content}, self.chunk_summary_prompt, with_json_parse=False
        )

        return [self._build_summary_subgraph(data, summary_name, summary, o_label)]

    @staticmethod
    def _build_summary_subgraph(data, summary_name, summary, o_label) -> SubGraph:
        """Assemble the Summary node + its childOf / sourceChunk edges.

        Shared by ``_invoke`` and ``_ainvoke`` so the two paths differ only in how
        the summary text is obtained.
        """
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

        return sub_graph
