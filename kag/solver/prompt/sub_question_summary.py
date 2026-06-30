from kag.interface import PromptABC


@PromptABC.register("default_sub_question_summary")
class SubQuestionSummary(PromptABC):
    template_en = """Please answer the question `$question` based on the retrieved knowledge graph and relevant documents, and combine historical information for comprehensive analysis.
Requirement:
1. Answer the question as directly as possible, without including any other information.
2. Do not repeat the content of the question.
3. Generate answers based on the provided information. If multiple answers are possible, generate all of them.
4. If there is no suitable answer, answer 'I don't know'.
5. Provide the answer and also provide the reason.
history:
$history

knowledge graph:
$knowledge_graph

docs:
$docs

answer:
"""

    @property
    def template_variables(self) -> list[str]:
        return ["history", "question", "knowledge_graph", "docs"]

    def parse_response(self, response: str, **kwargs):
        return response
