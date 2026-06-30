from abc import abstractmethod

from kag.common.registry import Registrable
from kag.interface.solver.base_model import SPOEntity
from kag.interface.solver.model.one_hop_graph import (
    EntityData,
    OneHopGraphData,
)


class GraphApiABC(Registrable):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @abstractmethod
    def get_entity_prop_by_id(self, biz_id, label) -> dict:
        pass

    @abstractmethod
    def get_entity(self, entity: SPOEntity) -> list[EntityData]:
        pass

    @abstractmethod
    def get_entity_one_hop(self, entity: EntityData) -> OneHopGraphData:
        pass

    @abstractmethod
    def calculate_pagerank_scores(
        self, target_vertex_type, start_nodes: list[dict], top_k=10
    ) -> dict:
        """Compute personalized PageRank scores from the given starting nodes.

        Args:
            target_vertex_type: Vertex type whose PageRank scores are returned.
            start_nodes: Starting nodes (e.g. document fragment IDs) seeding the
                PageRank walk.
            top_k: Maximum number of scored vertices to return.

        Returns:
            Mapping of vertex ID to its PageRank score. Empty when no start
            nodes are provided.
        """
