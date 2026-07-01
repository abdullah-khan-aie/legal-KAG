# Minimal stand-in for kag.common.config.LogicFormConfiguration.
#
# SchemaUtils reads only these attributes from the config object:
#   - prefix             namespace prefix stripped/added to labels
#   - schema_file_name   CSV schema path; "" selects the local-YAML loader
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
    # Server-free config object SchemaUtils reads. ``schema_file_name`` empty ("")
    # selects the local-YAML loader (LocalSchemaLoader); set it to use a CSV schema.
    def __init__(self, args=None):
        args = args or {}
        self.resource_path = args.get("resource_path", "./")
        self.prefix = args.get("prefix", "")
        self.schema_file_name = args.get("schema_file_name", "")
