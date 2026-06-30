import logging

from kag.interface import PromptABC

logger = logging.getLogger(__name__)


@PromptABC.register("default_deduce_multi_choice")
class DeduceMutiChoice(PromptABC):
    template_en = """You are a logical reasoning assistant. Please follow these strict instructions:

Analyze the provided [Information] which contains reference variables (e.g., o1, o2) with Q&A pairs.
Evaluate the [Question] which may reference these variables.
Based on the provided options and related variables, choose at least one option to respond to the question
If there are no available options, simply reply 'No relevant information' without explanation.
[Information]:
$memory

[Question]:
$instruction

Answer:"""

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
