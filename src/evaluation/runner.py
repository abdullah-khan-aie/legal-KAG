"""Run the goldset across query pipelines and score the answers.

Scores each answer four ways: exact match and token F1, a lenient substring
check, an LLM judge that tolerates paraphrase, and whether retrieval surfaced
the answer at all. Results are aggregated per pipeline and written as JSON, so
changes can be A/B tested against a baseline.

Needs the same environment as the server plus an already-ingested graph:
    python -m src.evaluation.runner --pipelines retriever --out results.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from kag.common.llm.anthropic_client import aclose_all_anthropic_clients
from kag.interface import LLMClient
from src.application.query.builder import chat_llm_config
from src.application.query.streaming import stream_query_events
from src.bootstrap import initialize_graph_schema
from src.config import get_settings
from src.evaluation.judge import judge_answer
from src.evaluation.metrics import contains_gold, get_em_f1, rouge_l

_GOLDSET = Path(__file__).parent / "goldset.json"


def load_goldset(path: Path = _GOLDSET) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


async def run_query(query: str, pipeline: str) -> str:
    """Run one query and return the final answer."""
    answer = ""
    async for event in stream_query_events(query, pipeline):
        segment = event.get("segment")
        content = event.get("content") or ""
        if segment == "done":
            answer = content
        elif segment == "error":
            answer = f"[error] {content}"
    return answer


def _build_judge_llm() -> LLMClient:
    # Ensure the anthropic client type is registered before from_config.
    import kag.common.llm.anthropic_client  # noqa: F401

    return LLMClient.from_config(chat_llm_config(get_settings()))


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 3) if values else 0.0


async def evaluate(pipelines: list[str], limit: int | None) -> dict[str, Any]:
    settings = get_settings()
    # Seed KAG_PROJECT_CONF (namespace/schema_path/chat_llm) + ensure indexes, since
    # we are not going through the FastAPI lifespan.
    initialize_graph_schema(settings)
    judge_llm = _build_judge_llm()

    goldset = load_goldset()
    if limit:
        goldset = goldset[:limit]

    results: list[dict[str, Any]] = []
    try:
        for pipeline in pipelines:
            for item in goldset:
                q, gold = item["question"], item["gold"]
                try:
                    answer = await run_query(q, pipeline)
                except Exception as err:  # keep going; record the failure
                    answer = f"[exception] {err}"
                em, f1 = get_em_f1(answer, gold)
                verdict = judge_answer(judge_llm, q, gold, answer)
                results.append(
                    {
                        "id": item["id"],
                        "tier": item["tier"],
                        "pipeline": pipeline,
                        "question": q,
                        "gold": gold,
                        "answer": answer,
                        "em": em,
                        "f1": round(f1, 3),
                        "contains": contains_gold(answer, gold),
                        "judge": verdict.correct,
                        "judge_reason": verdict.reason,
                        "rouge_l": rouge_l(answer, gold),
                    }
                )
    finally:
        await aclose_all_anthropic_clients()
    return {"results": results, "summary": _summarize(results)}


def _summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    by_pipeline: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_pipeline[r["pipeline"]].append(r)

    summary: dict[str, Any] = {}
    for pipeline, rows in by_pipeline.items():
        overall = {
            "n": len(rows),
            "em": _mean([r["em"] for r in rows]),
            "f1": _mean([r["f1"] for r in rows]),
            "contains": _mean([float(r["contains"]) for r in rows]),
            "judge_acc": _mean([float(r["judge"]) for r in rows]),
        }
        by_tier = {}
        for tier in sorted({r["tier"] for r in rows}):
            trows = [r for r in rows if r["tier"] == tier]
            by_tier[f"tier{tier}"] = {
                "n": len(trows),
                "judge_acc": _mean([float(r["judge"]) for r in trows]),
                "contains": _mean([float(r["contains"]) for r in trows]),
            }
        summary[pipeline] = {"overall": overall, "by_tier": by_tier}
    return summary


def _print_report(summary: dict[str, Any]) -> None:
    print("\n=== Accuracy summary (per pipeline) ===")
    header = f"{'pipeline':<14}{'n':>4}{'EM':>7}{'F1':>7}{'contains':>10}{'judge':>8}"
    print(header)
    print("-" * len(header))
    for pipeline, s in summary.items():
        o = s["overall"]
        print(
            f"{pipeline:<14}{o['n']:>4}{o['em']:>7}{o['f1']:>7}"
            f"{o['contains']:>10}{o['judge_acc']:>8}"
        )
    print("\n=== judge accuracy / contains by tier ===")
    for pipeline, s in summary.items():
        tiers = " | ".join(
            f"{t}: judge {v['judge_acc']} contains {v['contains']} (n={v['n']})"
            for t, v in s["by_tier"].items()
        )
        print(f"  {pipeline:<14} {tiers}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate query-pipeline accuracy on the goldset.")
    parser.add_argument(
        "--pipelines",
        nargs="+",
        default=["retriever", "deep_thought", "kag_thinker"],
        help="Pipelines to evaluate.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Only the first N goldset items.")
    parser.add_argument("--out", type=str, default="eval_results.json", help="Results JSON path.")
    args = parser.parse_args()

    report = asyncio.run(evaluate(args.pipelines, args.limit))
    Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    _print_report(report["summary"])
    print(f"\nWrote per-question results to {args.out}")


if __name__ == "__main__":
    main()
