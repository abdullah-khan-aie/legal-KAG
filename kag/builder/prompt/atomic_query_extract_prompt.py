from kag.interface import PromptABC


@PromptABC.register("atomic_query_extract")
class AtomicQueryExtractPrompt(PromptABC):
    """Ask the model for every answerable question a chunk supports.

    Used by ``AtomicQueryExtractor`` at ingest: each returned question becomes an
    ``AtomicQuery`` node linked back to the chunk, so query-time retrieval can
    match a user question against these pre-generated questions
    (question-to-question) rather than against raw chunk text. Output is newline
    separated (no JSON), so parsing cannot fail on a malformed reply.
    """

    template_en = """
# Task
Your task is to extract as many questions as possible that are relevant and can be answered by the given content. Please try to be diverse and avoid extracting duplicated or similar questions. Make sure your question contains necessary entity names and avoid using pronouns like it, he, she, they, the company, the person etc.

# Output Format
Output your answers line by line, with each question on a new line, without itemized symbols or numbers.

# Content
$content

# Output
"""

    @property
    def template_variables(self) -> list[str]:
        return ["content"]

    def parse_response(self, response: str, **kwargs):
        if not isinstance(response, str):
            return []
        return [line.strip() for line in response.split("\n") if line.strip()]
