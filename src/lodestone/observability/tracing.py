"""Langfuse tracing for the ingestion (and, later, query) pipelines.

Mirrors the professional pattern used in the ``doc_validation`` project:

* a cached ``get_langfuse()`` client whose keys come from settings (AWS Secrets
  Manager) and which is a no-op when ``enable_observability`` is off,
* thin helpers (:func:`span`, :func:`propagate`, :func:`current_parent`) that are
  zero-overhead no-ops when observability is disabled, so call sites stay clean.

Hierarchy produced for ingestion (see ``application/ingestion``):

    session "ingestion"
      └─ trace = client            (one per client folder, e.g. "Halgarth Estates")
           └─ span = document       (one per file)
                └─ read / split (no cost)
                └─ extract → generation per LLM call (Anthropic, token cost)
                └─ embed (Cohere usage) / align / postprocess / write

Unlike ``doc_validation`` (OpenAI, auto-instrumented) this app uses the Anthropic
Claude API + Cohere, so LLM/embedding generations are created explicitly at the
client call sites and token usage is attached to the current generation.
"""

from __future__ import annotations

import contextlib
from functools import lru_cache

# Fixed session ids: the session identifies the *pipeline*, so every ingestion
# run's traces live under one "ingestion" session and every query under "query".
INGESTION_SESSION = "ingestion"
QUERY_SESSION = "query"


@lru_cache(maxsize=1)
def observability_enabled() -> bool:
    """Whether tracing is on. Cheap, cached, and safe if settings can't load."""
    try:
        from src.lodestone.config.settings import get_settings

        return bool(get_settings().enable_observability)
    except Exception:
        return False


@lru_cache(maxsize=1)
def get_langfuse():
    """Return the process-wide Langfuse client, configured from settings.

    Keys are read from the ``lodestone/env`` secret (added out-of-band). Tracing is
    gated by ``enable_observability`` so a disabled client never emits.
    """
    from langfuse import Langfuse

    from src.lodestone.config.settings import get_settings

    s = get_settings()
    return Langfuse(
        public_key=s.langfuse_public_key.get_secret_value(),
        secret_key=s.langfuse_secret_key.get_secret_value(),
        host=s.langfuse_base_url.get_secret_value(),
        tracing_enabled=s.enable_observability,
        environment=s.environment,
    )


@contextlib.contextmanager
def span(name: str, as_type: str = "span", parent: dict | None = None, **attrs):
    """Nested observation as a context manager; a no-op when disabled.

    Yields the observation object (so callers can ``.update(...)`` usage/output),
    or ``None`` when observability is off. ``parent`` is a ``trace_context`` dict
    ``{"trace_id", "parent_span_id"}`` used to attach work that runs detached from
    the current context (e.g. the extraction worker pool).
    """
    if not observability_enabled():
        yield None
        return
    kwargs = dict(attrs)
    if parent:
        kwargs["trace_context"] = parent
    with get_langfuse().start_as_current_observation(as_type=as_type, name=name, **kwargs) as obs:
        yield obs


@contextlib.contextmanager
def propagate(session_id: str | None = None, **attrs):
    """Propagate ``session_id`` / metadata to all nested observations (no-op off).

    Note: Langfuse requires metadata keys to be alphanumeric and values to be
    strings <= 200 chars.
    """
    if not observability_enabled():
        yield
        return
    from langfuse import propagate_attributes

    with propagate_attributes(session_id=session_id, **attrs):
        yield


def current_parent() -> dict | None:
    """Capture the current observation as a ``trace_context`` dict, or ``None``.

    Used to re-attach spans created in a detached context (worker pool) back under
    the document's ``extract`` span.
    """
    if not observability_enabled():
        return None
    lf = get_langfuse()
    trace_id = lf.get_current_trace_id()
    parent_span_id = lf.get_current_observation_id()
    if not trace_id or not parent_span_id:
        return None
    return {"trace_id": trace_id, "parent_span_id": parent_span_id}


def _cost_details(kind, input_tokens, output_tokens):
    """USD cost from token counts x per-token price (from settings), or None.

    ``kind`` selects the price pair: ``"llm"`` uses the Anthropic in/out prices,
    ``"embed"`` uses the Cohere input price (no output). Langfuse doesn't know
    these models' prices, so we compute the dollar cost ourselves and pass it as
    cost_details (which Langfuse then aggregates up the trace).
    """
    try:
        from src.lodestone.config.settings import get_settings

        s = get_settings()
    except Exception:
        return None
    if kind == "embed":
        price_in, price_out = s.embed_cost_per_token, 0.0
    else:
        price_in, price_out = s.llm_input_cost_per_token, s.llm_output_cost_per_token
    cost: dict = {}
    if input_tokens:
        cost["input"] = input_tokens * price_in
    if output_tokens:
        cost["output"] = output_tokens * price_out
    if not cost:
        return None
    cost["total"] = round(sum(cost.values()), 10)
    return cost


def record_generation_usage(
    gen, *, model=None, input_tokens=None, output_tokens=None, output=None, kind="llm"
):
    """Attach model, token usage, computed dollar cost, and output to a generation."""
    if gen is None:
        return
    usage = {}
    if input_tokens is not None:
        usage["input"] = input_tokens
    if output_tokens is not None:
        usage["output"] = output_tokens
    payload: dict = {}
    if model:
        payload["model"] = model
    if usage:
        payload["usage_details"] = usage
    if output is not None:
        payload["output"] = output
    cost = _cost_details(kind, input_tokens, output_tokens)
    if cost:
        payload["cost_details"] = cost
    if payload:
        gen.update(**payload)


def flush() -> None:
    """Flush buffered spans. Required at the end of batch jobs (ingestion runs)."""
    if observability_enabled():
        try:
            get_langfuse().flush()
        except Exception:
            pass
