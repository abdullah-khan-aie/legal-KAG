from abc import abstractmethod

from kag_extracted.common.registry import Registrable


class SearchApiABC(Registrable):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @abstractmethod
    def search_text(self, query_string, label_constraints=None, topk=10, params=None) -> list:
        pass

    @abstractmethod
    def search_vector(
        self, label, property_key, query_vector, topk=10, ef_search=None, params=None
    ) -> list:
        pass

    @abstractmethod
    def search_custom(self, custom_query, params=None) -> list:
        pass
