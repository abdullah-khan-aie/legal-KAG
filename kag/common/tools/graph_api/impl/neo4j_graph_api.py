# Neo4j-backed GraphApiABC.
#
# The server impl (openspg_graph_api) routes every op through the Scala reasoner
# (execute_dsl). The server-free reference is MemoryGraphApi / MemoryGraph, which
# build EntityData / RelationData / OneHopGraphData directly from the graph store.
# This impl reproduces that construction on the extracted Neo4jClient:
#
#   * get_entity_one_hop  <- mirrors MemoryGraph.get_one_hop_graph
#   * _create_entity_from_node    <- mirrors MemoryGraph._create_entity_from_vertex
#   * _create_relation_from_edge  <- mirrors MemoryGraph._create_relation_from_edge
#   * calculate_pagerank_scores   <- Neo4jClient.get_pagerank_scores ({id: score},
#                                     the openspg_graph_api contract)
#
# The ONE adaptation vs the igraph reference: node *type* comes from the Neo4j
# node labels (labels(n) minus "Entity") rather than a "label" property, because
# Neo4j models the type as a label. This matches how the extracted
# Neo4jClient.vector_search already surfaces labels as "__labels__".

import logging

from kag_extracted.common.tools.graph_api.graph_api_abc import GraphApiABC
from kag_extracted.common.tools.graph_api.model.table_model import TableData
from kag_extracted.interface.solver.base_model import SPOEntity
from kag_extracted.interface.solver.model.one_hop_graph import (
    EntityData,
    OneHopGraphData,
    Prop,
    RelationData,
)

logger = logging.getLogger()


def _node_type_from_labels(labels, fallback=None):
    """First non-builtin label is the entity type (Neo4j models type as a label)."""
    for label in labels or []:
        if label == "Entity":
            continue
        return label
    return fallback


@GraphApiABC.register("neo4j_graph_api")
class Neo4jGraphApi(GraphApiABC):
    """``GraphApiABC`` backed by the extracted ``Neo4jClient`` graph store."""

    def __init__(self, graph_store, **kwargs):
        super().__init__(**kwargs)
        self.graph_store = graph_store

    # --- entity / relation construction (mirrors MemoryGraph) --------------- #
    @staticmethod
    def _create_entity_from_node(attributes: dict, labels, biz_id=None, label=None):
        entity = EntityData()
        entity.prop = Prop.from_dict(attributes, None, None)
        entity.biz_id = attributes.get("id", biz_id)
        entity.name = attributes.get("name", "")
        entity.description = attributes.get(
            "content", attributes.get("description", attributes.get("desc", ""))
        )
        entity.type = _node_type_from_labels(labels, label)
        entity.name_vec = attributes.get("_name_vector")
        entity.content_vec = attributes.get("_content_vector")
        entity.type_zh = None
        entity.score = 1.0
        return entity

    @staticmethod
    def _create_relation_from_edge(
        attributes: dict, rel_type, from_entity: EntityData, end_entity: EntityData
    ) -> RelationData:
        relation = RelationData()
        relation.prop = Prop.from_dict(attributes, None, None)
        relation.from_id = from_entity.biz_id
        relation.end_id = end_entity.biz_id
        relation.from_entity = from_entity
        relation.from_type = from_entity.type
        relation.from_alias = "s"
        relation.end_type = end_entity.type
        relation.end_entity = end_entity
        relation.end_alias = "o"
        relation.type = rel_type
        relation.type_zh = None
        return relation

    def _session(self):
        return self.graph_store._driver.session(database=self.graph_store._database)

    def get_entity(self, entity: SPOEntity) -> list[EntityData]:
        results: list[EntityData] = []
        types = entity.get_entity_type_set() or [None]
        for biz_id in entity.id_set:
            for entity_type in types:
                node = self.graph_store.get_node(entity_type, biz_id) if entity_type else None
                if node is None:
                    continue
                results.append(
                    self._create_entity_from_node(
                        dict(node), list(node.labels), biz_id, entity_type
                    )
                )
                break
        return results

    def get_entity_one_hop(self, entity: EntityData) -> OneHopGraphData:
        # mirrors MemoryGraph.get_one_hop_graph: start node + in/out edges
        query = (
            "MATCH (s {id: $sid}) "
            "OPTIONAL MATCH (s)-[r]-(n) "
            "RETURN s, labels(s) AS s_labels, r, type(r) AS r_type, "
            "startNode(r) = s AS is_out, n, labels(n) AS n_labels"
        )
        with self._session() as session:
            rows = session.run(query, sid=entity.biz_id).data()
        if not rows:
            return None
        start_attrs = rows[0]["s"]
        start_entity = self._create_entity_from_node(
            dict(start_attrs), rows[0]["s_labels"], entity.biz_id, entity.type
        )
        one_hop = OneHopGraphData(None, "s")
        one_hop.s = start_entity
        for row in rows:
            if row["r"] is None or row["n"] is None:
                continue
            neighbor = self._create_entity_from_node(dict(row["n"]), row["n_labels"])
            if row["is_out"]:
                relation = self._create_relation_from_edge(
                    dict(row["r"]), row["r_type"], start_entity, neighbor
                )
                one_hop.out_relations.setdefault(relation.type, []).append(relation)
            else:
                relation = self._create_relation_from_edge(
                    dict(row["r"]), row["r_type"], neighbor, start_entity
                )
                one_hop.in_relations.setdefault(relation.type, []).append(relation)
        return one_hop

    def calculate_pagerank_scores(
        self, target_vertex_type, start_nodes: list[dict], top_k=10
    ) -> dict:
        # openspg_graph_api contract: {biz_id: score}
        scored = self.graph_store.get_pagerank_scores(start_nodes, target_vertex_type)
        return {item["id"]: item["score"] for item in scored}

    def get_entity_prop_by_id(self, biz_id, label) -> dict:
        node = self.graph_store.get_node(label, biz_id)
        if node is None:
            return {}
        entity = self._create_entity_from_node(dict(node), list(node.labels), biz_id, label)
        datas = entity.to_json()
        if entity.prop:
            datas.update(entity.prop.get_properties_map())
        return datas

    def convert_spo_to_one_graph(self, table: TableData) -> dict[str, OneHopGraphData]:
        # DSL/table path is server (reasoner) only; server-free uses get_entity_one_hop.
        raise NotImplementedError(
            "convert_spo_to_one_graph requires the reasoner DSL path; use "
            "get_entity_one_hop in the Neo4j-backed build."
        )

    def execute_dsl(self, dsl: str, **kwargs) -> TableData:
        raise NotImplementedError(
            "execute_dsl runs KGDSL on the OpenSPG reasoner (Scala) engine, which is "
            "not available server-free; use the Neo4j graph ops instead."
        )
