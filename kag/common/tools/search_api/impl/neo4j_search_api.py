# Neo4j-backed SearchApiABC. Vector/text search runs in-process via
# Neo4jClient.vector_search / .text_search, which return records already shaped
# {"node": {..., "__labels__": [...]}, "score": ...}, so this class just
# delegates to the graph store.

from kag.common.tools.search_api.search_api_abc import SearchApiABC


@SearchApiABC.register("neo4j_search_api")
class Neo4jSearchApi(SearchApiABC):
    """``SearchApiABC`` backed by the ``Neo4jClient`` graph store."""

    def __init__(self, graph_store, **kwargs):
        super().__init__(**kwargs)
        self.graph_store = graph_store

    def search_text(self, query_string, label_constraints=None, topk=10, params=None):
        # ``params`` is the ABC's extension slot; callers use it to target a
        # specific full-text index (e.g. the dedicated chunk index) by name.
        index_name = (params or {}).get("index_name")
        return self.graph_store.text_search(
            query_string=query_string,
            label_constraints=label_constraints,
            topk=topk,
            index_name=index_name,
        )

    def search_vector(
        self, label, property_key, query_vector, topk=10, ef_search=None, params=None
    ):
        return self.graph_store.vector_search(
            label=label,
            property_key=property_key,
            query_text_or_vector=query_vector,
            topk=topk,
            ef_search=ef_search,
        )

    def search_custom(self, custom_query, params=None):
        # knext routes custom queries to the server; server-free, run via Neo4j.
        return self.graph_store.run_script(custom_query)
