import logging

from kag.builder.model.chunk import Chunk, ChunkTypeEnum
from kag.builder.model.sub_graph import SubGraph
from kag.common import Input, Output
from kag.interface import ExtractorABC
from kag.schema.client import CHUNK_TYPE, TABLE_TYPE

logger = logging.getLogger(__name__)


@ExtractorABC.register("outline_extractor")
class OutlineExtractor(ExtractorABC):
    def __init__(self):
        super().__init__()

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
        return ["outline_index"]

    def _invoke(self, input: Input, **kwargs) -> list[Output]:
        """Build an outline subgraph linking the chunk to its parent and source chunk.

        Args:
            input: The chunk to derive an outline node from.
        """
        if input.type == ChunkTypeEnum.Text:
            o_label = CHUNK_TYPE
        else:
            o_label = TABLE_TYPE
        outline_name = input.name

        index = outline_name.find("_split")
        if index != -1:
            outline_name = outline_name[:index]

        sub_graph = SubGraph([], [])
        # add Outline Node
        sub_graph.add_node(
            id=input.id,
            name=outline_name,
            label="Outline",
            properties={"id": input.id, "name": outline_name},
        )

        parent_id = getattr(input, "parent_id", None)
        if parent_id is not None:
            # add Outline_childOf_Outline edge
            sub_graph.add_edge(
                s_id=input.id,
                s_label="Outline",
                p="childOf",
                o_id=parent_id,
                o_label="Outline",
                properties={},
            )

        # add Outline_sourceChunk_Chunk edge
        sub_graph.add_edge(
            s_id=input.id,
            s_label="Outline",
            p="sourceChunk",
            o_id=f"{input.id}",
            o_label=o_label,
            properties={},
        )

        return [sub_graph]
