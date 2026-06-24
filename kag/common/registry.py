# Minimal stand-in for kag.common.registry.Registrable.
#
# The full kag Registrable is a ~1200-line config-driven registration/instantiation
# framework (from_config, type registry, lazy loading) coupled to KAG_PROJECT_CONF.
# The extracted retriever/solver code only needs Registrable as a base class that
# provides a no-op `register` decorator and a `from_config` hook. We construct the
# concrete impls explicitly (e.g. Neo4j-backed Search/Graph APIs) rather than by
# config type-name, so this minimal base preserves the inheritance + decorator
# surface without re-introducing the server/config coupling.


class Registrable:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    @classmethod
    def register(cls, name=None, *args, **kwargs):
        def _decorator(target):
            return target

        return _decorator

    @classmethod
    def from_config(cls, conf):
        # The real framework instantiates a registered subclass by {"type": ...}.
        # Here impls are bound explicitly; from_config is not used server-free.
        raise NotImplementedError(
            f"{cls.__name__}.from_config is not available in the extracted "
            "(config-free) build; construct the concrete implementation directly."
        )
