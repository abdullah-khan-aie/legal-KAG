from abc import ABC, abstractmethod


class GraphStore(ABC):
    """Define the standard interface for graph data operations.

    Subclasses must implement node CRUD, relationship handling, and index
    management against a concrete graph backend.
    """

    @abstractmethod
    def close(self):
        """Release the graph store resources."""

    @abstractmethod
    def initialize_schema(self, schema):
        """Initialize the graph schema.

        Args:
            schema: Definition of the graph schema.
        """

    @abstractmethod
    def upsert_node(self, label, properties, id_key="id", extra_labels=("Entity",)):
        """Insert or update a single node.

        Args:
            label: Label of the node.
            properties: Properties of the node.
            id_key: Property key used as the unique identifier.
            extra_labels: Additional labels for the node.
        """

    @abstractmethod
    def upsert_nodes(self, label, properties_list, id_key="id", extra_labels=("Entity",)):
        """Insert or update multiple nodes.

        Args:
            label: Label of the nodes.
            properties_list: List of properties for the nodes.
            id_key: Property key used as the unique identifier.
            extra_labels: Additional labels for the nodes.
        """

    @abstractmethod
    def batch_preprocess_node_properties(self, node_batch, extra_labels=("Entity",)):
        """Preprocess node properties in a batch.

        Args:
            node_batch: A batch of nodes.
            extra_labels: Additional labels for the nodes.
        """

    @abstractmethod
    def get_node(self, label, id_value, id_key="id"):
        """Get a node by label and identifier.

        Args:
            label: Label of the node.
            id_value: Unique identifier value of the node.
            id_key: Property key used as the unique identifier.

        Returns:
            The matching node.
        """

    @abstractmethod
    def delete_node(self, label, id_value, id_key="id"):
        """Delete a single node.

        Args:
            label: Label of the node.
            id_value: Unique identifier value of the node.
            id_key: Property key used as the unique identifier.
        """

    @abstractmethod
    def delete_nodes(self, label, id_values, id_key="id"):
        """Delete multiple nodes.

        Args:
            label: Label of the nodes.
            id_values: List of unique identifier values for the nodes.
            id_key: Property key used as the unique identifier.
        """

    @abstractmethod
    def upsert_relationship(
        self,
        start_node_label,
        start_node_id_value,
        end_node_label,
        end_node_id_value,
        rel_type,
        properties,
        upsert_nodes=True,
        start_node_id_key="id",
        end_node_id_key="id",
    ):
        """Insert or update a single relationship.

        Args:
            start_node_label: Label of the start node.
            start_node_id_value: Unique identifier value of the start node.
            end_node_label: Label of the end node.
            end_node_id_value: Unique identifier value of the end node.
            rel_type: Type of the relationship.
            properties: Properties of the relationship.
            upsert_nodes: Whether to insert or update the endpoint nodes.
            start_node_id_key: Property key used as the unique identifier for the start node.
            end_node_id_key: Property key used as the unique identifier for the end node.
        """

    @abstractmethod
    def upsert_relationships(
        self,
        start_node_label,
        end_node_label,
        rel_type,
        relationships,
        upsert_nodes=True,
        start_node_id_key="id",
        end_node_id_key="id",
    ):
        """Insert or update multiple relationships.

        Args:
            start_node_label: Label of the start node.
            end_node_label: Label of the end node.
            rel_type: Type of the relationship.
            relationships: List of relationships.
            upsert_nodes: Whether to insert or update the endpoint nodes.
            start_node_id_key: Property key used as the unique identifier for the start node.
            end_node_id_key: Property key used as the unique identifier for the end node.
        """

    @abstractmethod
    def delete_relationship(
        self,
        start_node_label,
        start_node_id_value,
        end_node_label,
        end_node_id_value,
        rel_type,
        start_node_id_key="id",
        end_node_id_key="id",
    ):
        """Delete a single relationship.

        Args:
            start_node_label: Label of the start node.
            start_node_id_value: Unique identifier value of the start node.
            end_node_label: Label of the end node.
            end_node_id_value: Unique identifier value of the end node.
            rel_type: Type of the relationship.
            start_node_id_key: Property key used as the unique identifier for the start node.
            end_node_id_key: Property key used as the unique identifier for the end node.
        """

    @abstractmethod
    def delete_relationships(
        self,
        start_node_label,
        start_node_id_values,
        end_node_label,
        end_node_id_values,
        rel_type,
        start_node_id_key="id",
        end_node_id_key="id",
    ):
        """Delete multiple relationships.

        Args:
            start_node_label: Label of the start node.
            start_node_id_values: List of unique identifier values for the start nodes.
            end_node_label: Label of the end node.
            end_node_id_values: List of unique identifier values for the end nodes.
            rel_type: Type of the relationship.
            start_node_id_key: Property key used as the unique identifier for the start node.
            end_node_id_key: Property key used as the unique identifier for the end node.
        """

    @abstractmethod
    def create_index(self, label, property_key, index_name=None):
        """Create a node index.

        Args:
            label: Label of the node.
            property_key: Property key used for indexing.
            index_name: Name of the index (optional).
        """

    @abstractmethod
    def create_text_index(self, labels, property_keys, index_name=None):
        """Create a text index.

        Args:
            labels: List of node labels.
            property_keys: List of property keys used for indexing.
            index_name: Name of the index (optional).
        """

    @abstractmethod
    def create_vector_index(
        self,
        label,
        property_key,
        index_name=None,
        vector_dimensions=768,
        metric_type="cosine",
        hnsw_m=None,
        hnsw_ef_construction=None,
    ):
        """Create a vector index.

        Args:
            label: Label of the node.
            property_key: Property key used for indexing.
            index_name: Name of the index (optional).
            vector_dimensions: Dimensionality of the vectors.
            metric_type: Distance measure used for similarity.
            hnsw_m: m parameter of the HNSW algorithm; None uses m=16.
            hnsw_ef_construction: ef_construction parameter of the HNSW algorithm; None uses ef_construction=100.
        """

    @abstractmethod
    def delete_index(self, index_name):
        """Delete an index by name.

        Args:
            index_name: Name of the index.
        """

    @abstractmethod
    def text_search(self, query_string, label_constraints=None, topk=10, index_name=None):
        """Perform a text search.

        Args:
            query_string: Query string.
            label_constraints: Label constraints (optional).
            topk: Number of top results to return.
            index_name: Name of the index (optional).

        Returns:
            List of search results.
        """

    @abstractmethod
    def vector_search(
        self,
        label,
        property_key,
        query_text_or_vector,
        topk=10,
        index_name=None,
        ef_search=None,
    ):
        """Perform a vector search.

        Args:
            label: Label of the node.
            property_key: Property key used for indexing.
            query_text_or_vector: Query text or vector.
            topk: Number of top results to return.
            index_name: Name of the index (optional).
            ef_search: ef_search parameter of the HNSW algorithm; number of candidates to consider.

        Returns:
            List of search results.
        """

    @abstractmethod
    def execute_pagerank(self, iterations=20, damping_factor=0.85):
        """Execute the PageRank algorithm.

        Args:
            iterations: Number of iterations.
            damping_factor: Damping factor.
        """

    @abstractmethod
    def get_pagerank_scores(self, start_nodes, target_type):
        """Get PageRank scores.

        Args:
            start_nodes: Start nodes.
            target_type: Target node type.

        Returns:
            PageRank scores.
        """

    @abstractmethod
    def run_script(self, script):
        """Execute a script.

        Args:
            script: Script to be executed.
        """

    @abstractmethod
    def get_all_entity_labels(self):
        """Get all entity labels.

        Returns:
            List of entity labels.
        """
