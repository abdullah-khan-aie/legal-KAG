import logging
from typing import Literal

from pydantic import BaseModel, Field

from kag.interface import PromptABC

logger = logging.getLogger(__name__)


class ThinkDecision(BaseModel):
    """One reasoning turn of the kag-thinker loop.

    Replaces the fine-tuned model's ``<search>...</search>`` / ``<answer>\\boxed{}``
    text protocol with an explicit, schema-validated decision so any model (not just
    KAG-Thinker) drives the retrieve-then-answer loop deterministically.
    """

    reasoning: str = Field(
        description="Brief step-by-step reasoning about the sub-question and what is or isn't known so far."
    )
    action: Literal["search", "answer"] = Field(
        description=(
            "'search' if you need to look information up in the knowledge base to answer; "
            "'answer' if the provided references (or prior turns) already let you answer."
        )
    )
    search_query: str | None = Field(
        default=None,
        description="When action='search': a focused natural-language query to retrieve from the knowledge base.",
    )
    answer: str | None = Field(
        default=None,
        description="When action='answer': the final answer to the sub-question, stated concisely.",
    )


@PromptABC.register("kag_subquestion_think")
class KagSubquestionThinkPrompt(PromptABC):
    template_en = """You are answering a sub-question step by step, and you may retrieve from a knowledge base.

For the current sub-question, decide one of two actions:
- If the information already available to you (the references provided so far, if any) is enough, choose action "answer" and give the concise final answer to the sub-question.
- If you still need to look something up, choose action "search" and give a focused search query; you will be given references and can then continue.

Only answer from the provided references or established facts; do not rely on outside/general knowledge for specific factual lookups (e.g. registration numbers, dates, names).

Question:
$question
"""

    @property
    def template_variables(self) -> list[str]:
        return ["question"]

    def output_schema(self):
        return ThinkDecision

    def parse_response(self, rsp, **kwargs):
        return rsp
