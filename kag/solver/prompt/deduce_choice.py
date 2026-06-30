import logging

from kag.interface import PromptABC

logger = logging.getLogger(__name__)


@PromptABC.register("default_deduce_choice")
class DeduceChoice(PromptABC):
    template_en = """Role:
You are a logical reasoning assistant designed to answer questions by selecting the correct one option from a set of possibilities based on provided reference data.

Instructions:
1.Analyze the [Information] section containing reference variables (e.g., o1, o2, o3) with Q&A pairs.
2.Evaluate the [Question] to determine:
    The type of selection (e.g., "earliest date", "highest score", "longest duration", "specific value").
    The relevant attribute (e.g., air date, rating, length, price).
3.Extract the values of the relevant attribute from the referenced variables.
4.Respond as follows:
    If one item meets the selection criteria: Output the full name of the selected option directly, don't output reference variables
    If no item meets the criteria or no data is available: Reply: "No relevant information" without explanation.
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
