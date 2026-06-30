import logging

from kag.interface import PromptABC

logger = logging.getLogger(__name__)


@PromptABC.register("default_deduce_extractor")
class DeduceExtractor(PromptABC):
    template_en = (
        "Based on the provided options and related answers, choose one option to respond to the question '$instruction'."
        "No explanation is needed;"
        "If there are no available options, simply reply 'No relevant information' without explanation."
        "\n[Information]: '$memory'"
        "\nEnsure that the information provided comes directly and accurately from the retrieved document, "
        "without any speculation."
    )

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
