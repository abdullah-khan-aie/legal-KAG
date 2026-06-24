from kag_extracted.interface import PromptABC


@PromptABC.register("default_chunk_summary")
class ChunkSummaryPrompt(PromptABC):
    template_zh = """You are an AI assistant. Your task is to generate a summary for the given text chunk content.

Requirements: Use the same language as the given content to generate the summary. Do not include prompt prefix words such as "summary" in the output.

Content of the given text chunk:
$content
"""

    template_en = """You are an AI assistant. Your task is to generate summary for the given text chunk content.

Requirements: Use the same language of the input content to generate summary. Omit prompt prefix words such as "summary".

Content of the given text chunk:
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
