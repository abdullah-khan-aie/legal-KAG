"""QA evaluation metrics (Exact Match, token-F1, ROUGE-L).

Ported from KAG's ``kag/common/benchmarks/evaUtils.py`` (the reusable, stack-agnostic
core), with the answer-normalization and F1 semantics kept identical so scores are
comparable to KAG's benchmark numbers. ROUGE is optional (only used if ``rouge`` is
installed).
"""

from __future__ import annotations

import re
import string
from collections import Counter


def normalize_answer(s: str) -> str:
    """Lowercase, strip articles/punctuation, and collapse whitespace (SQuAD-style)."""

    def remove_articles(text: str) -> str:
        return re.sub(r"\b(a|an|the)\b", " ", text)

    def white_space_fix(text: str) -> str:
        return " ".join(text.split())

    def remove_punc(text: str) -> str:
        exclude = set(string.punctuation)
        return "".join(ch for ch in text if ch not in exclude)

    return white_space_fix(remove_articles(remove_punc(str(s).lower())))


def exact_match_score(prediction: str, ground_truth: str) -> int:
    """1 if the normalized prediction equals the normalized ground truth, else 0."""
    return 1 if normalize_answer(prediction) == normalize_answer(ground_truth) else 0


def f1_score(prediction: str, ground_truth: str) -> tuple[float, float, float]:
    """Token-overlap F1 / precision / recall between prediction and ground truth."""
    norm_pred = normalize_answer(prediction)
    norm_gold = normalize_answer(ground_truth)
    zero = (0.0, 0.0, 0.0)

    # yes/no/noanswer answers must match exactly to score.
    for sentinel in ("yes", "no", "noanswer"):
        if (norm_pred == sentinel or norm_gold == sentinel) and norm_pred != norm_gold:
            return zero

    pred_tokens = norm_pred.split()
    gold_tokens = norm_gold.split()
    common = Counter(pred_tokens) & Counter(gold_tokens)
    num_same = sum(common.values())
    if num_same == 0 or not pred_tokens or not gold_tokens:
        return zero

    precision = num_same / len(pred_tokens)
    recall = num_same / len(gold_tokens)
    f1 = (2 * precision * recall) / (precision + recall)
    return f1, precision, recall


def get_em_f1(prediction: str, gold: str) -> tuple[float, float]:
    """Return (EM, F1) for a single prediction/gold pair."""
    em = exact_match_score(prediction, gold)
    f1, _, _ = f1_score(prediction, gold)
    return float(em), f1


def contains_gold(prediction: str, gold: str) -> bool:
    """Lenient hit: the normalized gold answer appears within the normalized prediction.

    Useful for verbose answers (e.g. "the registration number is 12784563") where EM
    is 0 but the answer is clearly present.
    """
    return normalize_answer(gold) in normalize_answer(prediction)


def rouge_l(prediction: str, gold: str) -> float | None:
    """ROUGE-L F if the optional ``rouge`` package is available, else None."""
    try:
        from rouge import Rouge
    except Exception:
        return None
    pred = prediction.strip() or "empty"
    ref = gold.strip() or "empty"
    try:
        return Rouge().get_scores(pred, ref)[0]["rouge-l"]["f"]
    except Exception:
        return None
