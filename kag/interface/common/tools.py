from kag.common.registry import Registrable


class ToolABC(Registrable):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._name: str = kwargs.get("name", "")

    @property
    def name(self):
        return self._name if self._name else self.schema().get("name", "")

    def invoke(self, query, **kwargs):
        raise NotImplementedError("invoke not implemented yet.")

    async def ainvoke(self, query, **kwargs):
        raise NotImplementedError("ainvoke not implemented yet.")

    def schema(self):
        return {}
