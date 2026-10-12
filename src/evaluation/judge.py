"""LLM-as-judge for answer correctness.

Ported in spirit from KAG's ``JudgerPrompt`` (kag/common/benchmarks): given a
question, the gold answer, and a model prediction, decide whether the prediction is
correct. Verbose/redundant predictions count as correct as long as they contain and
do not contradict the gold answer. Uses our structured-output path (Bedrock tool-use)
so the verdict is a validated boolean rather than parsed free text.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from kag.interface import LLMClient, PromptABC


class Judgment(BaseModel):
    correct: bool = Field(
        description="True if the prediction correctly answers the question per the gold answer."
    )
    reason: str = Field(default="", description="One short sentence justifying the verdict.")


@PromptABC.register("eval_judger")
class JudgerPrompt(PromptABC):
    template_en = """You are grading a question-answering system.

Given a Question, the correct Gold answer, and a model Prediction, decide whether the
Prediction is correct. Rules:
- The Prediction is correct if it contains the gold answer and does not contradict it.
- Extra detail, restatement, or explanation in the Prediction is fine.
- If the Prediction gives a different value, or says it cannot find / does not know the
  answer, it is incorrect.

Question:
$question

Gold answer:
$gold

Prediction:
$prediction
"""

    @property
    def template_variables(self) -> list[str]:
        return ["question", "gold", "prediction"]

    def output_schema(self):
        return Judgment

    def parse_response(self, rsp, **kwargs):
        return rsp


def judge_answer(llm: LLMClient, question: str, gold: str, prediction: str) -> Judgment:
    """Return the judge's verdict for one (question, gold, prediction) triple."""
    prompt = JudgerPrompt()
    result = llm.invoke(
        {"question": question, "gold": gold, "prediction": prediction},
        prompt,
        with_except=True,
    )
    if isinstance(result, Judgment):
        return result
    # Defensive fallback if a non-structured client is ever used.
    return Judgment(correct=bool(result), reason="")
