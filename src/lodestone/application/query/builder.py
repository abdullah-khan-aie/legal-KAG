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


def chat_llm_config(settings: Settings) -> dict[str, Any]:
    """Config dict the registry uses to build the Anthropic Claude LLM client.

    Throughput is bounded solely by the extraction concurrency (``model_execute_num``);
    there is no client-side rate limiter.
    """
    config = {
        "type": "anthropic",
        "model": settings.llm_model,
    }
    config.update(_anthropic_credentials(settings))
    return config


def vectorize_model_config(settings: Settings, input_type: str) -> dict[str, Any]:
    """Config dict for the direct Cohere embedder (``input_type="query"`` for retrieval)."""
    config = {
        "type": "cohere",
        "model": settings.embed_model,
        "input_type": input_type,
        "output_dimension": settings.embed_dimension,
    }
    config.update(_cohere_credentials(settings))
    return config


def _anthropic_credentials(settings: Settings) -> dict[str, Any]:
    """Anthropic API key from settings, or empty to fall back to ANTHROPIC_API_KEY.

    The ``SecretStr`` (not the plaintext) is placed in the client config, so the
    value stays masked as ``**********`` in any logs; the client unwraps it only at
    the point it constructs the Anthropic SDK client.
    """
    if settings.anthropic_api_key:
        return {"api_key": settings.anthropic_api_key}
    return {}


def _cohere_credentials(settings: Settings) -> dict[str, Any]:
    """Cohere API key from settings, or empty to fall back to the SDK's CO_API_KEY.

    The ``SecretStr`` (not the plaintext) is placed in the client config, so the
    value stays masked as ``**********`` in any logs; the model unwraps it only at
    the point it constructs the Cohere SDK client.
    """
    if settings.cohere_api_key:
        return {"api_key": settings.cohere_api_key}
    return {}


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
    """Import indexer/solver/tool modules so their ``@register`` decorators populate the registry."""
    from kag.common.registry import import_modules_from_path

    for path in (
        "kag/indexer",
        "kag/solver",
        "kag/common/tools",
        "kag/common/llm",
        "kag/common/vectorize_model",
    ):
        import_modules_from_path(path)


def _build_retriever_configs(
    index_list: list[str],
    llm_config: dict[str, Any],
    vectorize_config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Assemble the ``{retrievers}`` list from the active indices.

    For each index name, build its ``KAGIndexManager`` and collect that index's
    retriever config(s). This is the query-side half of the extractor/retriever
    symmetry: the retrievers that run are exactly the ones matching the indices
    that were built at ingest time.
    """
    from kag.indexer import KAGIndexManager

    configs: list[dict[str, Any]] = []
    for index_name in index_list:
        manager = KAGIndexManager.from_config(
            {
                "type": index_name,
                "llm_config": llm_config,
                "vectorize_model_config": vectorize_config,
            }
        )
        configs.extend(manager.build_retriever_config(llm_config, vectorize_config))
    return configs


def _inject_graph_store(node: Any, graph_store) -> None:
    """Attach the live graph store to every Neo4j search/graph API in the config.

    The retrievers are built by the registry from config dicts several levels
    deep, where a live ``Neo4jClient`` can't be expressed. Rather than a global,
    we walk the resolved config and pass the store explicitly to each
    ``neo4j_search_api`` / ``neo4j_graph_api`` node before it is constructed.
    """
    if isinstance(node, dict):
        if node.get("type") in ("neo4j_search_api", "neo4j_graph_api"):
            node["graph_store"] = graph_store
        for value in node.values():
            _inject_graph_store(value, graph_store)
    elif isinstance(node, list):
        for item in node:
            _inject_graph_store(item, graph_store)


def build_query_pipeline(
    pipeline_name: str = "retriever",
    settings: Settings | None = None,
    graph_store=None,
):
    """Construct a KAG solver pipeline for the given pipeline definition.

    Args:
        pipeline_name: Which ``pipelineconf`` definition to build (e.g. "retriever",
            "deep_thought", "kag_thinker", "naive_rag").
        settings: Settings to source model credentials and the active ``index_list``
            from; defaults to the singleton.
        graph_store: Live Neo4j graph store, injected into the config-built
            ``neo4j_search_api`` / ``neo4j_graph_api`` retrievers.

    Returns:
        A ``SolverPipelineABC`` instance ready to answer queries.
    """
    from kag.interface import SolverPipelineABC

    settings = settings or get_settings()
    _register_components()
    chat_llm = chat_llm_config(settings)
    vectorize_model = vectorize_model_config(settings, input_type="query")
    replacements = {
        "chat_llm": chat_llm,
        "vectorize_model": vectorize_model,
        "retrievers": _build_retriever_configs(settings.index_list, chat_llm, vectorize_model),
    }
    conf = _replace_placeholders(_load_pipeline_conf(pipeline_name), replacements)
    solver_conf = conf["solver_pipeline"]
    if graph_store is not None:
        _inject_graph_store(solver_conf, graph_store)
    return SolverPipelineABC.from_config(solver_conf)
