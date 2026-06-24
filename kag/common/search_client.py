# Server-free SearchClient.
#
# knext/search/client.py SearchClient is a thin REST wrapper: it builds a
# VectorSearchRequest/TextSearchRequest, POSTs it to the OpenSPG server, and maps
# each returned record with idx_record_to_dict:
#       {"score": record.score, "node": record.fields}
# The actual vector/text search runs in the server, backed by Neo4j.
#
# KAG already ships that exact search in Python: Neo4jClient.vector_search /
# .text_search (kag/common/graphstore/neo4j_graph_store.py, extracted verbatim).
# Neo4jClient.vector_search already returns records shaped {"node": {...,
# "__labels__": [...]}, "score": ...} — identical to idx_record_to_dict's output —
# so this client is a faithful delegation, not a reimplementation.

from kag_extracted.interface import SearchClientABC


class Neo4jSearchClient(SearchClientABC):
    """``SearchClientABC`` backed by the extracted ``Neo4jClient`` graph store.

    Reproduces knext ``SearchClient`` semantics without the OpenSPG server: the
    request/REST round-trip is replaced by a direct ``GraphStore`` call, which is
    the same query the server issued on the client's behalf.
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
