# SearchClient that runs vector/text search in-process against Neo4j
# (Neo4jClient.vector_search / .text_search) instead of over the network. Those
# methods return records already shaped {"node": {..., "__labels__": [...]},
# "score": ...}, which is what callers here expect.

from kag.interface import SearchClientABC


class Neo4jSearchClient(SearchClientABC):
    """``SearchClientABC`` backed by the extracted ``Neo4jClient`` graph store.

    Replaces the REST round-trip with a direct ``GraphStore`` call, which issues
    the same query.
    """

    def __init__(self, graph_store):
        self.graph_store = graph_store

    def search_vector(
        self, label, property_key, query_vector, topk=10, ef_search=None, params=None
    ):
        # knext passed `params` to the server; Neo4jClient.vector_search takes none.
        return self.graph_store.vector_search(
            label=label,
            property_key=property_key,
            query_text_or_vector=query_vector,
            topk=topk,
            ef_search=ef_search,
        )

    def search_text(self, query_string, label_constraints=None, topk=10, params=None):
        return self.graph_store.text_search(
            query_string=query_string,
            label_constraints=label_constraints,
            topk=topk,
        )
