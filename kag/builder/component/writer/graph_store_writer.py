"""Server-free SubGraph writer.

``KGWriter`` (kag/builder/component/writer/kg_writer.py) persists a SubGraph by
POSTing it to the OpenSPG Java server via ``GraphClient.write_graph``; the server
then maps the SubGraph onto graph-store ``upsert_nodes`` / ``upsert_relationships``
calls. That mapping is the only part of the write path that lives in Java rather
than Python.

This writer reproduces it against the (server-free) ``GraphStore`` interface,
following the actual server source rather than guessing:

  * ``format_label`` / ``standarlize_graph`` are copied verbatim from ``KGWriter``
    (kag/builder/component/writer/kg_writer.py) — label namespacing + JSON-
    serialization of non-string properties. The only difference is that
    ``namespace`` is supplied to ``__init__`` instead of read from
    ``KAG_PROJECT_CONF``.
  * ``_write_nodes`` / ``_write_edges`` mirror ``Neo4jSinkWriter.writeNode`` /
    ``writeEdge`` (openspg builder/runner/local .../sink/impl/Neo4jSinkWriter.java)
    — skip blank id/name/label, merge id+name into properties, then
    ``upsertVertex`` / ``upsertEdge`` (== ``upsert_nodes`` / ``upsert_relationships``).
  * the server ``write_graph`` REST call is replaced by direct
    ``GraphStore.initialize_schema`` + upsert calls — the work the Java server
    did on receipt of the POST.

Everything else (the GraphStore / Neo4jClient implementation) is the extracted
kag code, unchanged.
"""

import json
import logging
from collections import defaultdict

from kag.builder.model.sub_graph import SubGraph
from kag.common.graphstore.graph_store import GraphStore

logger = logging.getLogger(__name__)


class GraphStoreWriter:
    """Write a :class:`SubGraph` into a :class:`GraphStore` (e.g. ``Neo4jClient``).

    Args:
        graph_store: A bound ``GraphStore`` implementation (Neo4jClient, ...).
        schema: Optional ``{type_name: SpgType}`` mapping from
            ``SchemaClient.load()``; when given, indices are created once via
            ``graph_store.initialize_schema`` before the first write.
        namespace: Project namespace used by ``format_label`` (mirrors
            ``KAG_PROJECT_CONF.namespace``). Empty string disables prefixing.
    """

    def __init__(self, graph_store: GraphStore, schema=None, namespace: str = ""):
        self.graph_store = graph_store
        self.schema = schema
        self.namespace = namespace
        self._schema_initialized = False

    # --- verbatim from KGWriter (namespace now an attribute) ---------------- #
    def format_label(self, label: str):
        """
        Formats the label by adding the project namespace if it is not already present.
        """
        namespace = self.namespace
        if not namespace:
            return label
        if label.split(".")[0] == namespace:
            return label
        return f"{namespace}.{label}"

    def standarlize_graph(self, graph):
        for node in graph.nodes:
            node.label = self.format_label(node.label)
        for edge in graph.edges:
            edge.from_type = self.format_label(edge.from_type)
            edge.to_type = self.format_label(edge.to_type)

        for node in graph.nodes:
            for k, v in node.properties.items():
                if k.startswith("_"):
                    continue
                if not isinstance(v, str):
                    node.properties[k] = json.dumps(v, ensure_ascii=False)
        for edge in graph.edges:
            for k, v in edge.properties.items():
                if k.startswith("_"):
                    continue
                if not isinstance(v, str):
                    edge.properties[k] = json.dumps(v, ensure_ascii=False)

        return graph

    # --- the mapping Neo4jSinkWriter.writeNode/writeEdge performs ----------- #
    # Source: builder/runner/local/.../sink/impl/Neo4jSinkWriter.java
    #   writeNode: skip blank id/name/label; put id+name into properties;
    #              upsertVertex(label, [record]).
    #   writeEdge: skip blank from/to/label; upsertEdge from (fromType,label,toType).
    # (labelPrefix re-prefixing and convertProperties type-normalization are
    #  idempotent / Java-JSON-specific and already handled by standarlize_graph.)
    @staticmethod
    def _is_blank(value) -> bool:
        return value is None or (isinstance(value, str) and value.strip() == "")

    def _write_nodes(self, graph: SubGraph) -> None:
        by_label = defaultdict(list)
        for node in graph.nodes:
            if self._is_blank(node.id) or self._is_blank(node.name) or self._is_blank(node.label):
                logger.info("write Node ignore node id:%s", node.id)
                continue
            props = dict(node.properties)
            props["id"] = node.id
            props["name"] = node.name
            by_label[node.label].append(props)
        for label, properties_list in by_label.items():
            self.graph_store.upsert_nodes(label, properties_list)

    def _write_edges(self, graph: SubGraph) -> None:
        by_key = defaultdict(list)
        for edge in graph.edges:
            if (
                self._is_blank(edge.from_id)
                or self._is_blank(edge.to_id)
                or self._is_blank(edge.label)
            ):
                logger.info("write Edge ignore edge from:%s to:%s", edge.from_id, edge.to_id)
                continue
            key = (edge.from_type, edge.to_type, edge.label)
            by_key[key].append(
                {
                    "start_node_id": edge.from_id,
                    "end_node_id": edge.to_id,
                    "properties": dict(edge.properties),
                }
            )
        for (start_label, end_label, rel_type), relations in by_key.items():
            self.graph_store.upsert_relationships(start_label, end_label, rel_type, relations)

    def _invoke(self, input: SubGraph, **kwargs) -> list[SubGraph]:
        if self.schema is not None and not self._schema_initialized:
            self.graph_store.initialize_schema(self.schema)
            self._schema_initialized = True
        graph = self.standarlize_graph(input)
        self._write_nodes(graph)
        self._write_edges(graph)
        return [graph]

    def invoke(self, input: SubGraph, **kwargs) -> list[SubGraph]:
        return self._invoke(input, **kwargs)
