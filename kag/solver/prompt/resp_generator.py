import logging

from kag.interface import PromptABC

logger = logging.getLogger(__name__)


@PromptABC.register("default_resp_generator")
class RespGenerator(PromptABC):
    template_en = (
        "Answer the question based on the given reference."
        "\nGive me the answer and why."
        "\nThe following are given reference:'$memory'\nQuestion: '$instruction'"
    )

    @property
    def template_variables(self) -> list[str]:
        return ["memory", "instruction"]

    def parse_response(self, response: str, **kwargs):
        logger.debug(f"reasoner output:{response}")
        return response

    def is_json_format(self):
        return False
