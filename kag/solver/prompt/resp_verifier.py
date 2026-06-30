import logging

from kag.interface import PromptABC

logger = logging.getLogger(__name__)


@PromptABC.register("default_resp_verifier")
class RespVerifier(PromptABC):
    template_en = (
        "Judging based solely on the current known information and without allowing for inference, "
        "are you able to respond completely and accurately to the question '$sub_instruction'? \n"
        "Known information: '$supporting_fact'. If yes, please reply with 'Yes', followed by an accurate response to the question '$sub_instruction', "
        "without restating the question; if no, please reply with 'No' directly."
    )

    @property
    def template_variables(self) -> list[str]:
        return ["sub_instruction", "supporting_fact"]

    def parse_response_en(self, satisfied_info: str):
        if satisfied_info[:3] == "Yes":
            satisfied = True
        else:
            satisfied = False
        if satisfied:
            satisfied_info = satisfied_info.replace("Yes", "").strip()
            res = "The answer to the Question'{}' is '{}'".format(
                self.template_variables_value["sub_instruction"], satisfied_info
            )
            return res
        return None

    def parse_response(self, response: str, **kwargs):
        logger.debug(f"reasoner output:{response}")
        return self.parse_response_en(response)
