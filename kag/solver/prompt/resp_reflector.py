import logging

from kag.interface import PromptABC

logger = logging.getLogger(__name__)


@PromptABC.register("default_resp_reflector")
class RespReflector(PromptABC):
    template_en = (
        "You serve as an intelligent assistant, adept at facilitating users through complex, "
        "multi-hop reasoning across multiple documents. Please understand the information gap between the currently known information and the target problem."
        "Your task is to generate one thought in the form of question for next retrieval step directly. "
        "DON'T generate the whole thoughts at once!\n[Known information]: $memory\n[Target question]: $instruction\n[You Thought]:"
    )

    @property
    def template_variables(self) -> list[str]:
        return ["memory", "instruction"]

    @staticmethod
    def parse_response_en(response: str):
        update_reason_path = []
        split_path = response.split("\n")
        for p in split_path:
            if "Here are the steps" in p or p == "\n" or p == "":
                continue
            else:
                update_reason_path.append(p)
        logger.debug(f"cur path:{str(update_reason_path)}")
        return update_reason_path

    def parse_response(self, response: str, **kwargs):
        logger.debug(f"infer result:{response}")
        return self.parse_response_en(response)
