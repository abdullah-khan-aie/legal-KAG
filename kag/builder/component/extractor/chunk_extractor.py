import logging

from kag.builder.model.chunk import Chunk, ChunkTypeEnum
from kag.builder.model.sub_graph import SubGraph
from kag.common import Input, Output
from kag.interface import ExtractorABC

logger = logging.getLogger(__name__)


@ExtractorABC.register("chunk_extractor")
class ChunkExtractor(ExtractorABC):
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
        return ["chunk_index"]

    def _invoke(self, input: Input, **kwargs) -> list[Output]:
        """Wrap a text chunk into a single-node ``Chunk`` subgraph.

        Non-text chunks are skipped and yield an empty result.

        Args:
            input: The chunk to process.
        """
        text_chunk: Chunk = input
        if text_chunk.type != ChunkTypeEnum.Text:
            # only process text
            return []

        outline_name = input.name

        if "_split" in outline_name:
            outline_name = outline_name[: outline_name.find("_split")]

        sub_graph = SubGraph([], [])
        # add Outline Node
        sub_graph.add_node(
            id=f"{input.id}",
            name=outline_name,
            label="Chunk",
            properties={
                "id": input.id,
                "name": outline_name,
                "content": f"{outline_name}\n{input.content}",
            },
        )

        return [sub_graph]
