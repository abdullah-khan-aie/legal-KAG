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
    """Config dict the registry uses to build the Bedrock Claude LLM client.

    Carries kag's request-limiter knobs (``max_rate`` / ``time_period``). Every
    extractor client the registry builds from this config shares one AsyncLimiter
    keyed by client name, so these bound the process-global call rate across all
    extraction sub-calls -- the account-level throttle control (see
    ``model_execute_num`` for the complementary concurrency bound).
    """
    return {
        "type": "bedrock_claude",
        "region": settings.bedrock_region,
        "model": settings.llm_model,
        "max_rate": settings.llm_max_rate,
        "time_period": settings.llm_time_period,
    }


def vectorize_model_config(settings: Settings, input_type: str) -> dict[str, Any]:
    """Config dict for the Bedrock Cohere embedder (``input_type="query"`` for retrieval)."""
    return {
        "type": "bedrock_cohere",
        "region": settings.embed_region,
        "model": settings.embed_model,
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

    Mirrors ``main_solver.do_qa_pipeline``: for each index name, build its
    ``KAGIndexManager`` and collect that index's retriever config(s). This is
    the query-side half of the extractor/retriever symmetry -- the retrievers
    that run are exactly the ones matching the indices that were built.
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
