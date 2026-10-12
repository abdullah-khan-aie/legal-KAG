"""Langfuse tracing for the ingestion pipeline.

Every helper is a no-op when observability is off, so call sites need no guards.
Ingestion produces one "ingestion" session holding a trace per document, a span
per pipeline stage, and a generation carrying tokens and cost per model call.
"""

from __future__ import annotations

import contextlib
from functools import lru_cache

# The session identifies the pipeline, not the run, so every run lands together.
INGESTION_SESSION = "ingestion"
QUERY_SESSION = "query"


@lru_cache(maxsize=1)
def observability_enabled() -> bool:
    """Whether tracing is on. Returns False rather than raising if settings fail."""
    try:
        from src.config import get_settings

        return bool(get_settings().enable_observability)
    except Exception:
        return False


@lru_cache(maxsize=1)
def get_langfuse():
    """Return the process-wide Langfuse client, configured from the secret."""
    from langfuse import Langfuse

    from src.config import get_settings

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
    """Open a nested observation, yielding it so callers can attach usage.

    Yields None when tracing is off. Pass parent to attach work that runs
    detached from the current context, such as the extraction worker pool.
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
    """Apply session_id and metadata to everything nested inside.

    Langfuse rejects non-alphanumeric metadata keys and values over 200 chars.
    """
    if not observability_enabled():
        yield
        return
    from langfuse import propagate_attributes

    with propagate_attributes(session_id=session_id, **attrs):
        yield


def current_parent() -> dict | None:
    """Capture the current observation so detached work can re-attach to it."""
    if not observability_enabled():
        return None
    lf = get_langfuse()
    trace_id = lf.get_current_trace_id()
    parent_span_id = lf.get_current_observation_id()
    if not trace_id or not parent_span_id:
        return None
    return {"trace_id": trace_id, "parent_span_id": parent_span_id}


def _cost_details(kind, input_tokens, output_tokens):
    """Price the tokens using the per-token rates from settings.

    Langfuse cannot price these models itself, so we supply the dollar amounts
    and it aggregates them up the trace.
    """
    try:
        from src.config import get_settings

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
    """Attach model, token usage, cost and output to a generation."""
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
    """Send buffered spans. Batch jobs must call this or lose the tail of a run."""
    if observability_enabled():
        try:
            get_langfuse().flush()
        except Exception:
            pass
