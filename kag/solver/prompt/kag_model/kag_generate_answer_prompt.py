import logging

from kag.interface import PromptABC

logger = logging.getLogger(__name__)


@PromptABC.register("kag_generate_answer")
class KagGenerateAnswerPrompt(PromptABC):
    template_en = """Answer the last question based on question, the first n sub-questions and their answers (indicated by #n), and wrap the result with <answer>\\boxed{your answer}</answer>. 
question:
$question
sub-questions:
$sub_questions
last-question:
$last_question
answer:
"""

    @property
    def template_variables(self) -> list[str]:
        return ["last_question", "sub_questions", "question"]

    def parse_response(self, response: str, **kwargs):
        return response
