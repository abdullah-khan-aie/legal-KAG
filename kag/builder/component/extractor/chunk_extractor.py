import logging

from kag_extracted.builder.model.chunk import Chunk, ChunkTypeEnum
from kag_extracted.builder.model.sub_graph import SubGraph
from kag_extracted.common import Input, Output
from kag_extracted.interface import ExtractorABC

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
        """
        Invokes the semantic extractor to process input data.

        Args:
            input (Input): Input data containing name and content.
            **kwargs: Additional keyword arguments.

        Returns:
            List[Output]: A list of processed results, containing subgraph information.
        """
        text_chunk: Chunk = input
        if text_chunk.type != ChunkTypeEnum.Text:
            # only process text
            return []

        # if "/" not in input.name:
        outline_name = input.name
        # else:
        #     outline_name = input.name.split("/")[-1]

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
