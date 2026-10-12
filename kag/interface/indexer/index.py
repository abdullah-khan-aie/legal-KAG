# ruff: noqa
from typing import List
from kag.common.registry import Registrable


class IndexABC(Registrable):
    """
    An abstract base class that defines the interface for indices.
    """

    @property
    def description(self) -> str:
        return ""

    @property
    def cost(self) -> str:
        return ""

    @property
    def schema(self) -> List[str]:
        return []
