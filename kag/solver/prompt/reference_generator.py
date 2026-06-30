import logging

from kag.common.utils import get_now
from kag.interface import PromptABC

logger = logging.getLogger(__name__)


@PromptABC.register("default_refer_generator_prompt")
class ReferGeneratorPrompt(PromptABC):
    template_en = (
        f"You are an information analysis expert, today is {get_now(language='en')}."
        """Answer the question based on the given references.
If the answer contains referenced information, include the `id` field from the reference. If it is not a retrieved result, no citation marker is needed.
Do not repeat the references when outputting the answer.
Citations should be in the format `<reference id="chunk:1_2"></reference>`, and the cited symbol must exist in the `id` field of the references; otherwise, no citation should be provided.
If the question cannot be answered using the given references, use internal model knowledge to respond but clearly indicate whether the response is based on retrieved content or cited documents.

Example 1:
Task Process Context: Based on common knowledge, the father-in-law is the father of one's spouse. Therefore, we first need to find John's spouse, and then find the father of the spouse.
Given references:
reference:
[
    {
        "content": "John's wife is Mary",
        "document_name": "Introduction to John",
        "id": "chunk:1_1"
    },
    {
        "content": "Mary's father is Robert",
        "document_name": "Introduction to John",
        "id": "chunk:1_2"
    }
]
Question: 'Who is John's father-in-law?'

John's wife is Mary <reference id="chunk:1_1"></reference>, and Mary's father is Robert <reference id="chunk:1_2"></reference>. Therefore, John's father-in-law is Robert.

Example 2:
Task Process Context: Based on common knowledge, the father-in-law is the father of one's spouse. Therefore, we first need to find John's spouse, and then find the father of the spouse.
Given references:
reference:
[
    {
        "content": "John's wife is Mary",
        "document_name": "Introduction to John",
        "id": "chunk:1_1"
    },
    {
        "content": "Mary's father is Robert",
        "document_name": "Introduction to John",
        "id": "chunk:1_2"
    }
]
Question: 'John的岳父是谁'

John的妻子是Mary <reference id="chunk:1_1"></reference>, Mary的父亲是Robert <reference id="chunk:1_2"></reference>. 所以John的岳父是Robert.


The tone of the response should be smooth and natural, avoiding any mechanical feel, and the language of the output should match the language of the question.
Task Process Context: '$content'
Given references: '$ref'
Question: '$query'
"""
    )

    @property
    def template_variables(self) -> list[str]:
        return ["content", "query", "ref"]

    def parse_response(self, response: str, **kwargs):
        logger.debug(f"reasoner output:{response}")
        return response
