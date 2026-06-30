import logging

from kag.interface import PromptABC

logger = logging.getLogger(__name__)


@PromptABC.register("default_resp_extractor")
class RespExtractor(PromptABC):
    template_en = (
        "Known information:\n $supporting_fact\nYour job is to act as a professional writer. "
        "You will write a good-quality passage that can support the given prediction about the question only based on the information in the provided supporting passages. "
        "Now, let's start. After you write, please write [DONE] to indicate you are done. Do not write a prefix (e.g., 'Response:'') while writing a passage.\nQuestion:$instruction\nPassage:"
    )

    @property
    def template_variables(self) -> list[str]:
        return ["supporting_fact", "instruction"]

    def parse_response(self, response: str, **kwargs):
        logger.debug(f"reasoner output:{response}")
        return response
