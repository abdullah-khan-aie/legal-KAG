import logging

from kag.interface import PromptABC

logger = logging.getLogger(__name__)


@PromptABC.register("default_deduce_judge")
class DeduceJudge(PromptABC):
    template_en = """You are a logical reasoning assistant. Please follow these strict instructions:

Analyze the provided [Information] which contains reference variables (e.g., o1, o2) with Q&A pairs.
Evaluate the [Question] which may reference these variables.
Output only one of these three values:
Yes if the information confirms the statement in the question
No if the information contradicts the statement
No relevant information if the question cannot be answered with the given data
[Information]:
$memory

[Question]:
$instruction

Answer:
{Output only Yes/No/No relevant information}
"""

    @property
    def template_variables(self) -> list[str]:
        return ["memory", "instruction"]

    @staticmethod
    def parse_response_en(satisfied_info: str):
        if satisfied_info.startswith("No relevant information"):
            if_answered = False
        else:
            if_answered = True
        return if_answered, satisfied_info

    def parse_response(self, response: str, **kwargs):
        logger.debug(f"reasoner output:{response}")
        return self.parse_response_en(response)
