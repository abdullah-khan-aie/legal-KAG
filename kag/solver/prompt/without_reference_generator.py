import logging

from kag.common.utils import get_now
from kag.interface import PromptABC

logger = logging.getLogger(__name__)


@PromptABC.register("default_without_refer_generator_prompt")
class WithOutReferGeneratorPrompt(PromptABC):
    template_en = (
        f"You are an information analysis expert, today is {get_now(language='en')}."
        """Answer the question based on the given context.
Do not repeat the references when outputting the answer.

Example 1:
Task Process Context: 'After calculation by the calculator, 9.2 is greater than 9.1.'
Given references: ''
Question: 'Which is larger, 9.1 or 9.2?'
Answer: 9.2 is larger.

The tone of the response should be smooth and natural, avoiding any mechanical feel, and the language of the output should match the language of the question.
Task process contextual information: '$content'
Question: '$query'

"""
    )

    @property
    def template_variables(self) -> list[str]:
        return ["content", "query", "ref"]

    def parse_response(self, response: str, **kwargs):
        logger.debug(f"reasoner output:{response}")
        return response
