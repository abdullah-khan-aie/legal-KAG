import logging

from kag.interface import PromptABC

logger = logging.getLogger(__name__)


@PromptABC.register("kag_subquestion_think")
class KagSubquestionThinkPrompt(PromptABC):
    template_en = """Can you answer the following questions step by step? If you can, wrap your answer with <answer>\boxed{your answer}</answer>. If you can't, just reply that based on my internal knowledge, I can't answer this question, I need to retrieve external knowledge. 
Question: 
$question
"""

    @property
    def template_variables(self) -> list[str]:
        return ["question"]

    def parse_response(self, response: str, **kwargs):
        return response
