import logging

from tenacity import retry, stop_after_attempt

from kag.builder.model.sub_graph import SubGraph
from kag.common import KAGConstants, get_vector_field_name
from kag.interface import ExternalGraphLoaderABC, PostProcessorABC, SearchClientABC
from kag.schema.client import OTHER_TYPE, SchemaClient

logger = logging.getLogger()


@PostProcessorABC.register("base", as_default=True)
@PostProcessorABC.register("kag_post_processor")
class KAGPostProcessor(PostProcessorABC):
    """Post-process subgraphs: filter invalid data and link entities.

    Linking is done by vector similarity and, optionally, against an external graph.
    """

    def __init__(
        self,
        similarity_threshold: float = None,
        external_graph: ExternalGraphLoaderABC = None,
        **kwargs,
    ):
        """Initialize the post-processor and its similarity search client.

        Args:
            similarity_threshold: Minimum score for entity linking; ``None``
                disables similarity linking (filter-only).
            external_graph: External graph loader for external-graph-based linking.
        """
        super().__init__(**kwargs)
        self.namespace = kwargs.get("namespace", "")
        self.schema = SchemaClient(schema_path=kwargs.get("schema_path")).load()
        self.similarity_threshold = similarity_threshold
        self.external_graph = external_graph
        # bindable seam: pass search_client=<your store-backed SearchClientABC>
        # to enable similarity linking; default no-op = filter-only.
        self._search_client = kwargs.get("search_client") or SearchClientABC()

    def format_label(self, label: str):
        """Prefix the label with the project namespace if not already present.

        Args:
            label: The label to format.
        """
        namespace = self.namespace
        if label.split(".")[0] == namespace:
            return label
        return f"{namespace}.{label}"

    def _init_search(self):
        """Initializes the search client for entity linking (bindable seam)."""
        self._search_client = SearchClientABC()

    def filter_invalid_data(self, graph: SubGraph):
        """Drop nodes/edges missing required fields and normalize unknown labels.

        Args:
            graph: The subgraph to filter.
        """
        valid_nodes = []
        valid_edges = []
        for node in graph.nodes:
            if not node.id or not node.label:
                continue
            if node.label not in self.schema:
                node.label = self.format_label(OTHER_TYPE)
            valid_nodes.append(node)
        for edge in graph.edges:
            if edge.label:
                valid_edges.append(edge)
        return SubGraph(nodes=valid_nodes, edges=valid_edges)

    @retry(stop=stop_after_attempt(3), reraise=True)
    def _entity_link(self, graph: SubGraph, property_key: str = "name", labels: list[str] = None):
        """Link nodes to similar existing nodes via vector search.

        Args:
            graph: The subgraph to link entities in.
            property_key: The property whose vector is used for linking.
            labels: Labels to search within; ``None`` uses each node's own label.
        """
        vector_field_name = get_vector_field_name(property_key)
        for node in graph.nodes:
            if labels is None:
                link_labels = [self.format_label(node.label)]
            else:
                link_labels = [self.format_label(x) for x in labels]
            vector = node.properties.get(vector_field_name)
            if vector:
                all_similar_nodes = []
                for label in link_labels:
                    similar_nodes = self._search_client.search_vector(
                        label=label,
                        property_key=property_key,
                        query_vector=[float(x) for x in vector],
                        topk=1,
                        params={},
                    )
                    all_similar_nodes.extend(similar_nodes)
                for item in all_similar_nodes:
                    score = item["score"]
                    if score >= self.similarity_threshold and node.id != item["node"]["id"]:
                        graph.add_edge(
                            node.id,
                            node.label,
                            KAGConstants.KAG_SIMILAR_EDGE_NAME,
                            item["node"]["id"],
                            item["node"]["__labels__"][0],
                        )

    def similarity_based_link(self, graph: SubGraph, property_key: str = "name"):
        """Link entities to similar nodes within the same label.

        Args:
            graph: The subgraph to link entities in.
            property_key: The property whose vector is used for linking.
        """
        self._entity_link(graph, property_key, None)

    def external_graph_based_link(self, graph: SubGraph, property_key: str = "name"):
        """Link entities to nodes restricted to the external graph's allowed labels.

        Does nothing if no external graph is configured.

        Args:
            graph: The subgraph to link entities in.
            property_key: The property whose vector is used for linking.
        """
        if not self.external_graph:
            return
        labels = self.external_graph.get_allowed_labels()
        self._entity_link(graph, property_key, labels)

    def _invoke(self, input, **kwargs):
        """Filter the subgraph and, when a threshold is set, link its entities.

        Args:
            input: The subgraph to process.
        """
        origin_num_nodes = len(input.nodes)
        origin_num_edges = len(input.edges)
        new_graph = self.filter_invalid_data(input)
        if self.similarity_threshold is not None:
            self.similarity_based_link(new_graph)
            self.external_graph_based_link(new_graph)
        new_num_nodes = len(new_graph.nodes)
        new_num_edges = len(new_graph.edges)
        logger.debug(
            f"origin: {origin_num_nodes}/{origin_num_edges}, processed: {new_num_nodes}/{new_num_edges}"
        )
        return [new_graph]
