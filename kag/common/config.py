# Minimal stand-in for kag.common.config.LogicFormConfiguration.
#
# SchemaUtils reads only these attributes from the config object:
#   - prefix             namespace prefix stripped/added to labels
#   - project_id         project identifier
#   - host_addr          server address (only used by the get_schema_from_spg path)
#   - schema_file_name   CSV schema path; "" selects the server (spg) path
# This carries those fields without the OpenSPG config/server framework.


def get_default_chat_llm_config():
    """Stand-in for kag.common.config.get_default_chat_llm_config.

    In kag this returns the project's default chat-LLM config dict (consumed by
    ``LLMClient.from_config(...)`` as a fallback when no llm is passed). Server-free
    we bind the LLMClient explicitly, so this default is never instantiated; it
    returns an empty config to satisfy the import + fallback expression.
    """
    return {}


def get_default_vectorize_model_config():
    """Stand-in for the default vectorize-model config (see above)."""
    return {}


class LogicFormConfiguration:
    # Mirrors kag.common.config.LogicFormConfiguration's dict contract (same keys),
    # but server-free: it does NOT raise when KAG_PROJECT_ID / KAG_PROJECT_HOST_ADDR
    # are absent (the originals raise to enforce the server). schema_file_name selects
    # SchemaUtils' CSV path; leave it set (or bind a schema source) to avoid the
    # reasoner (get_schema_from_spg) path when constructing retrievers server-free.
    def __init__(self, args=None):
        args = args or {}
        self.resource_path = args.get("resource_path", "./")
        self.prefix = args.get("prefix", "")
        self.project_id = args.get("KAG_PROJECT_ID", None)
        self.schema_file_name = args.get("schema_file_name", "")
        self.host_addr = args.get("KAG_PROJECT_HOST_ADDR", None)
