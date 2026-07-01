import logging

from kag.builder.model.chunk import Chunk, ChunkTypeEnum
from kag.builder.model.sub_graph import SubGraph
from kag.common import Input, Output
from kag.interface import ExternalGraphLoaderABC, ExtractorABC
from kag.schema.client import CHUNK_TYPE

logger = logging.getLogger(__name__)


@ExtractorABC.register("naive_rag_extractor")
class NaiveRagExtractor(ExtractorABC):
    """Extract chunk-only subgraphs for naive RAG, optionally delegating tables.

    Attributes:
        external_graph: External graph loader used for additional NER.
        table_extractor: Extractor used to process table chunks.
    """

    def __init__(
        self,
        external_graph: ExternalGraphLoaderABC = None,
        table_extractor: ExtractorABC = None,
    ):
        """Initialize the extractor with optional external graph and table extractor.

        Args:
            external_graph: External graph loader for additional NER.
            table_extractor: Extractor for processing table chunks.
        """
        super().__init__()
        self.external_graph = external_graph
        self.table_extractor = table_extractor

    @property
    def input_types(self) -> type[Input]:
        return Chunk

    @property
    def output_types(self) -> type[Output]:
        return SubGraph

    @staticmethod
    def output_indices() -> list[str]:
        return ["chunk_index"]

    @staticmethod
    def assemble_sub_graph_with_chunk(sub_graph: SubGraph, chunk: Chunk):
        """Add the chunk as a node and link every existing node to it as its source.

        Args:
            sub_graph: The subgraph to add the chunk information to.
            chunk: The chunk providing the text and metadata.

        Returns:
            The updated subgraph.
        """
        for node in sub_graph.nodes:
            sub_graph.add_edge(node.id, node.label, "source", chunk.id, CHUNK_TYPE)
        sub_graph.add_node(
            chunk.id,
            chunk.name,
            CHUNK_TYPE,
            {
                "id": chunk.id,
                "name": chunk.name,
                "content": f"{chunk.name}\n{chunk.content}",
                **chunk.kwargs,
            },
        )
        sub_graph.id = chunk.id
        return sub_graph

    def _invoke(self, data: Input, **kwargs) -> list[Output]:
        """Build a chunk-only subgraph, delegating table chunks to the table extractor.

        Args:
            data: The chunk to process.
        """
        if self.table_extractor is not None and data.type == ChunkTypeEnum.Table:
            return self.table_extractor._invoke(data)

        out = []
        sub_graph = SubGraph([], [])
        sub_graph = self.assemble_sub_graph_with_chunk(sub_graph, data)

        out.append(sub_graph)
        return out
