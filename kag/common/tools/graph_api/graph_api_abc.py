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
        """
        Calculate and retrieve PageRank scores for the given starting nodes.

        Parameters:
        target_vertex_type (str): Return target vectex type ppr score
        start_nodes (list): A list containing document fragment IDs to be used as starting nodes for the PageRank algorithm.

        Returns:
        ppr_doc_scores (dict): A dictionary containing each document fragment ID and its corresponding PageRank score.

        This method uses the PageRank algorithm in the graph store to compute scores for document fragments. If `start_nodes` is empty,
        it returns an empty dictionary. Otherwise, it attempts to retrieve PageRank scores from the graph store and converts the result
        into a dictionary format where keys are document fragment IDs and values are their respective PageRank scores. Any exceptions,
        such as failures in running `run_pagerank_igraph_chunk`, are logged.
        """
