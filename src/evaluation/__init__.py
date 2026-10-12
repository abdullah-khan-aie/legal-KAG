"""Accuracy evaluation for the query pipelines.

Metrics and an LLM judge scored against our own goldset, not the public
benchmark datasets. Run with:

    python -m src.evaluation.runner
"""

from src.evaluation.metrics import (
    contains_gold,
    exact_match_score,
    f1_score,
    get_em_f1,
    normalize_answer,
    rouge_l,
)

__all__ = [
    "normalize_answer",
    "exact_match_score",
    "f1_score",
    "get_em_f1",
    "contains_gold",
    "rouge_l",
]
