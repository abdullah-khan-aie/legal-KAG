# Neo4j-backed SearchClientABC for entity linking.
#
# KAGPostProcessor links entities by calling search_client.search_vector(...) and
# connecting nodes whose name embedding is similar to an existing entity. KAG's
# server impl routed this through OpenSPG's ElasticSearch SearchClient; server-free
# we delegate to the same Neo4j vector search the retriever already uses
# (Neo4jClient.vector_search). Its records are already shaped
# {"node": {..., "__labels__": [...]}, "score": ...} -- exactly what _entity_link
# consumes -- so this is a faithful delegation, not a new search.

from kag.interface import SearchClientABC


class Neo4jSearchClient(SearchClientABC):
    """``SearchClientABC`` backed by the extracted ``Neo4jClient`` graph store."""

    def __init__(self, graph_store):
        self.graph_store = graph_store

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
