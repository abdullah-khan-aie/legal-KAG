"""Build a KAG solver (query/retrieval) pipeline from settings — server-free.

Mirrors upstream ``main_solver`` without its server/index coupling: it loads a
pipeline definition from ``kag/solver/pipelineconf/<name>.yaml``, substitutes the
``{chat_llm}`` / ``{vectorize_model}`` placeholders with configs built from our
settings (Azure OpenAI LLM + Azure Cohere embedder), and hands the result to
``SolverPipelineABC.from_config`` — the registry then instantiates the whole
pipeline (executors, retrievers, generator) by type.

The embedder is configured with ``input_type="query"`` here (the user's question
is a search query), whereas ingestion embeds chunks with ``input_type="document"``.
"""

from __future__ import annotations

import os
from typing import Any

from src.lodestone.config.settings import Settings, get_settings

# Pipeline name -> yaml file under kag/solver/pipelineconf/.
_PIPELINE_FILES = {
    "naive_rag": "naive_rag.yaml",
    "kag_thinker": "kag_thinker.yaml",
    "deep_thought": "deep_thought.yaml",
    "mcp": "mcp.yaml",
    "retriever": "retriever.yaml",
    "self_cognition": "self_cognition.yaml",
}


def _chat_llm_config(settings: Settings) -> dict[str, Any]:
    """Config dict the registry uses to build the Azure OpenAI LLM client."""
    return {
        "type": "azure_openai",
        "api_key": settings.llm_api_key.get_secret_value(),
        "base_url": settings.llm_base_url,
        "model": settings.llm_model,
        "azure_deployment": settings.llm_azure_deployment,
        "api_version": settings.llm_api_version,
    }


def _vectorize_model_config(settings: Settings, input_type: str) -> dict[str, Any]:
    """Config dict for the Azure Cohere embedder (``input_type="query"`` for retrieval)."""
    return {
        "type": "azure_cohere",
        "endpoint": settings.cohere_endpoint,
        "api_key": settings.cohere_api_key.get_secret_value(),
        "input_type": input_type,
    }


def _replace_placeholders(config: Any, replacements: dict[str, Any]) -> Any:
    """Recursively substitute ``"{name}"`` strings with ``replacements[name]``."""
    if isinstance(config, dict):
        return {k: _replace_placeholders(v, replacements) for k, v in config.items()}
    if isinstance(config, list):
        return [_replace_placeholders(item, replacements) for item in config]
    if isinstance(config, str) and config.startswith("{") and config.endswith("}"):
        key = config[1:-1]
        if key not in replacements:
            raise RuntimeError(f"Pipeline placeholder '{key}' has no replacement.")
        return replacements[key]
    return config


def _load_pipeline_conf(pipeline_name: str) -> dict[str, Any]:
    """Load and parse the pipeline definition yaml for ``pipeline_name``."""
    import yaml

    from kag.solver import pipelineconf

    if pipeline_name not in _PIPELINE_FILES:
        raise ValueError(
            f"Unknown pipeline '{pipeline_name}'; choose from {sorted(_PIPELINE_FILES)}."
        )
    conf_dir = os.path.dirname(pipelineconf.__file__)
    path = os.path.join(conf_dir, _PIPELINE_FILES[pipeline_name])
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _register_components() -> None:
    """Import solver/tool modules so their ``@register`` decorators populate the registry."""
    from kag.common.registry import import_modules_from_path

    for path in ("kag/solver", "kag/common/tools", "kag/common/llm", "kag/common/vectorize_model"):
        import_modules_from_path(path)


def build_query_pipeline(pipeline_name: str = "naive_rag", settings: Settings | None = None):
    """Construct a KAG solver pipeline for the given pipeline definition.

    Args:
        pipeline_name: Which ``pipelineconf`` definition to build (e.g. "naive_rag").
        settings: Settings to source model credentials from; defaults to the singleton.

    Returns:
        A ``SolverPipelineABC`` instance ready to answer queries.
    """
    from kag.interface import SolverPipelineABC

    settings = settings or get_settings()
    _register_components()
    replacements = {
        "chat_llm": _chat_llm_config(settings),
        "vectorize_model": _vectorize_model_config(settings, input_type="query"),
    }
    conf = _replace_placeholders(_load_pipeline_conf(pipeline_name), replacements)
    return SolverPipelineABC.from_config(conf["solver_pipeline"])
