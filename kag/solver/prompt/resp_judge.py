import logging

from kag.interface import PromptABC

logger = logging.getLogger(__name__)


@PromptABC.register("default_resp_judge")
class RespJudge(PromptABC):
    template_en = (
        "Judging based solely on the current known information and without allowing for inference, "
        "are you able to completely and accurately respond to the question '$instruction'? "
        "\nKnown information: '$memory'. "
        "\nIf you can, please reply with 'Yes' directly; "
        "if you cannot and need more information, please reply with 'No' directly."
    )

    @property
    def template_variables(self) -> list[str]:
        return ["memory", "instruction"]

    @staticmethod
    def parse_response_en(satisfied_info: str):
        if satisfied_info[:3] == "Yes":
            if_finished = True
        else:
            if_finished = False
        return if_finished

    def parse_response(self, response: str, **kwargs):
        logger.debug(f"reasoner output:{response}")
        return self.parse_response_en(response)
