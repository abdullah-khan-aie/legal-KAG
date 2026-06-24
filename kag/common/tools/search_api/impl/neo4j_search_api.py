# Neo4j-backed SearchApiABC.
#
# knext openspg_search_api / SearchClient route search through the OpenSPG server,
# mapping each result with idx_record_to_dict -> {"score": ..., "node": ...}.
# The actual vector/text search is Neo4jClient.vector_search / .text_search
# (extracted verbatim from kag), whose result records are already shaped
# {"node": {..., "__labels__": [...]}, "score": ...} -- identical to what the
# server returned. This impl is therefore a faithful delegation, not a new search.

from kag_extracted.common.tools.search_api.search_api_abc import SearchApiABC


@SearchApiABC.register("neo4j_search_api")
class Neo4jSearchApi(SearchApiABC):
    """``SearchApiABC`` backed by the extracted ``Neo4jClient`` graph store."""

    def __init__(self, graph_store, **kwargs):
        super().__init__(**kwargs)
        self.graph_store = graph_store

    def search_text(self, query_string, label_constraints=None, topk=10, params=None):
        return self.graph_store.text_search(
            query_string=query_string,
            label_constraints=label_constraints,
            topk=topk,
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
