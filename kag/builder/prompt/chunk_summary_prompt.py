from kag.interface import PromptABC


@PromptABC.register("default_chunk_summary")
class ChunkSummaryPrompt(PromptABC):
    template_en = """You are an AI assistant. Your task is to generate a summary for the content of a given text snippet.

Requirements: Generate the summary in the same language as the given content, and do not include any leading prompt such as "Content Summary" in the output.

Text snippet content:
$content
"""

    @property
    def template_variables(self) -> list[str]:
        return ["content"]

    def parse_response(self, response: str, **kwargs):
        try:
            response = response.strip()
            return response
        except Exception as e:
            print(e)
            return ""
