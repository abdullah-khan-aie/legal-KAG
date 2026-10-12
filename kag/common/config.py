# Minimal stand-in for kag.common.config.LogicFormConfiguration.
#
# SchemaUtils reads only these attributes from the config object:
#   - prefix             namespace prefix stripped/added to labels
#   - schema_file_name   CSV schema path; "" selects the local-YAML loader


def get_default_chat_llm_config(task_id=None):
    """Return the project's default chat-LLM config dict (upstream behaviour).

    Consumed by ``LLMClient.from_config(...)`` as the fallback when an executor is
    built without an explicit llm (e.g. the summary / context-select LLMs of
    ``KAGHybridRetrievalExecutor`` when ``enable_summary`` is on and the pipeline
    yaml doesn't wire them). Most of the server-free build binds the LLM
    explicitly via the ``{chat_llm}`` placeholder, but this fallback must still
    resolve to the real client -- so the app seeds it into the kag runtime config
    at the composition root (``bootstrap.initialize_graph_schema``). We raise
    rather than return ``{}`` so a missing seed fails loudly at build time instead
    of surfacing as a ``NotImplementedError`` from a bare base client when called.
    """
    from kag.common.conf import KAGConfigAccessor

    all_config = KAGConfigAccessor.get_config(task_id).all_config
    if "chat_llm" in all_config:
        return all_config["chat_llm"]
    if "llm" in all_config:
        return all_config["llm"]
    raise RuntimeError(
        "default chat_llm config not found; seed it at startup via "
        "KAG_CONFIG.all_config['chat_llm'] (see bootstrap.initialize_graph_schema)."
    )


class LogicFormConfiguration:
    # Server-free config object SchemaUtils reads. ``schema_file_name`` empty ("")
    # selects the local-YAML loader (LocalSchemaLoader); set it to use a CSV schema.
    def __init__(self, args=None):
        args = args or {}
        self.resource_path = args.get("resource_path", "./")
        self.prefix = args.get("prefix", "")
        self.schema_file_name = args.get("schema_file_name", "")
