import logging

from kag.interface import PromptABC

logger = logging.getLogger(__name__)


@PromptABC.register("default_deduce_entail")
class DeduceEntail(PromptABC):
    template_en = """You are a logical reasoning assistant. Please follow these strict instructions:

Analyze the provided [Information] which contains reference variables (e.g., o1, o2) with Q&A pairs.
Evaluate the [Question] which may reference these variables.
Analyze with rules:
1.If you can directly answer, reply with the answer without any explanation
2.If you cannot answer directly but there is related information, summarize the key information related to the question and clearly explain why it is related
3.If there is no relevant information, reply begin with 'No relevant information' and with explanation
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
