from kag.interface import PromptABC


@PromptABC.register("default_summary_question")
class SummaryQuestionWithOutSPO(PromptABC):
    template_en = """Please answer the question `$question` based on the retrieved relevant documents, and combine historical information for comprehensive analysis.
Requirement:
1.Do not repeat the content of the question.
2.Generate answers strictly based on provided information. If multiple answers are possible, list all plausible answers.
3.If no suitable answer exists, analyze related content based on document information.
4.Provide the answer along with the reasoning.
5.Output format should not have line breaks.

history:
$history

docs:
$docs

answer:
"""

    @property
    def template_variables(self) -> list[str]:
        return ["history", "question", "docs"]

    def parse_response(self, response: str, **kwargs):
        return response
