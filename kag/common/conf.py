# Minimal stand-in for kag.common.conf (KAGConstants / KAGConfigAccessor).
#
# The full kag conf is the config framework (KAG_PROJECT_CONF, task registry) the
# project deliberately does not re-introduce. The extracted retriever/solver code
# reads only a few constants and a config object exposing global_config (namespace,
# project_id, host_addr, language, biz_scene) and all_config. In the server-free
# build, models/schema are bound explicitly, so this returns a default config and
# the `... or X.from_config(...)` fallbacks in the extracted code never fire.


class KAGConstants:
    KAG_SIMILAR_EDGE_NAME = "similar"
    KAG_QA_TASK_CONFIG_KEY = "KAG_QA_TASK_CONFIG_KEY"
    PROJECT_CONFIG_KEY = "project"


class KAGGlobalConf:
    def __init__(self, **kwargs):
        import os

        self.namespace = kwargs.get("namespace", "")
        # dummy project id: verbatim kag does int(project_id); host_addr stays
        # None so server-detection (needs both id+addr) still resolves server-free.
        self.project_id = kwargs.get("project_id", "1")
        self.host_addr = kwargs.get("host_addr", None)
        self.language = kwargs.get("language", "en")
        self.biz_scene = kwargs.get("biz_scene", "default")
        # server-free schema source for SchemaUtils (read via ReasonerClient).
        # Set this (or INGEST_SCHEMA_PATH) to the local YAML schema so the solver
        # / retrievers build their SchemaUtils without the OpenSPG reasoner server.
        self.schema_path = kwargs.get("schema_path", os.environ.get("INGEST_SCHEMA_PATH", ""))
        for k, v in kwargs.items():
            setattr(self, k, v)


class KAGConfigMgr:
    def __init__(self, **kwargs):
        self.global_config = KAGGlobalConf(**kwargs)
        self._all_config = {}

    @property
    def all_config(self):
        return self._all_config


_DEFAULT_CONFIG = KAGConfigMgr()

# module-level singletons mirroring kag.common.conf (server-free defaults)
KAG_CONFIG = _DEFAULT_CONFIG
KAG_PROJECT_CONF = _DEFAULT_CONFIG.global_config


class KAGConfigAccessor:
    @staticmethod
    def get_config(task_with_kb_id=None) -> KAGConfigMgr:
        # Server-free: a single default config; impls are constructed explicitly.
        return _DEFAULT_CONFIG
