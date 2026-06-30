from kag.interface import PromptABC


@PromptABC.register("default_output_question")
class OutputQuestionPrompt(PromptABC):
    template_en = """Please answer the question “$question” based on the retrieved relevant documents and combine it with historical information for comprehensive analysis. The requirements are as follows:
1.Do not repeat the content of the question.
2.Generate answers based on the provided information. If there are multiple possible answers, generate all of them.
3、If there is no suitable answer, analyze relevant content based on the document information.
4.If the context is empty, respond based on the model's internal knowledge.
5.When outputting, use a sentence structure similar to this: "Based on the question, I first considered xxx, then yyy, and finally zzz. In conclusion, therefore mmmm."
6.The tone of the response should be smooth and natural, avoiding any mechanical feel.

Context: 
$context

Answer:
"""

    @property
    def template_variables(self) -> list[str]:
        return ["context", "question"]

    def parse_response(self, response: str, **kwargs):
        return response
