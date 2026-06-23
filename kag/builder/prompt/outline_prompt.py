import ast

from kag.interface import PromptABC


@PromptABC.register("outline")
class OutlinePrompt(PromptABC):
    template_en = """
{
    "instruction": "\nGiven a text content, please extract the titles and return them as a list. Each title should include the following information:\n- Title text\n- Title level (e.g., 1 for first level, 2 for second level, etc.)\n\nAssume titles follow these rules:\n1. Titles usually contain numbers. Since our text might be OCR-generated from images, titles may be hidden within paragraphs. Try to identify these numbered titles hidden in paragraphs.\n2. Title levels can be inferred through:\n   - Level 1: Usually document-level content.\n   - Level 2: Usually chapter-level content, with concise descriptions, sometimes starting with \"Part X\", \"Chapter X\", etc.\n   - Level 3 and below: Usually paragraph or detail-level titles, may include numerical prefixes (like \"1.\" or \"1.1\") or longer specific descriptions.\n3. Title levels can also be determined by context:\n   - If the text between two titles is very short, the latter title might be of higher or same level.\n   - Consecutively numbered titles (like \"Article 1\", \"Article 2\") are usually of the same level.\n   - Title hierarchy is often determined by number levels, e.g., \"1\", \"1.1\", \"1.1.1\" are levels 1, 2, 3 respectively.\n   - Titles containing keywords like \"Part\", \"Chapter\", \"Section\" with moderate length (5-20 characters) often have higher levels than longer or shorter titles.\n4. Ignore the following titles:\n   - Pure numbers or titles consisting only of numbers and punctuation (e.g., \"1.\", \"2.1\").\n   - Repeated titles (e.g., headers/footers misidentified as titles).\n5. If content cannot be clearly identified as a title or doesn't match these rules, ignore it.\n\nPlease return a list of titles with their corresponding levels in the following format:\n[\n    (\"Title text 1\", 1),\n    (\"Title text 2\", 2),\n    (\"Title text 3\", 3),\n    ...\n]. I will also provide the previously extracted outline as current_outlines, and you need to judge the granularity and corresponding levels of title extraction based on the current outline.",
    "input": "$input",
    "current_outline": "$current_outline",
    "example": [
        {
            "input": "Article 8 Principles\n\n1. In formulating or amending their laws and regulations...\n\nPart Two: Standards Concerning the Availability, Scope and Use of Intellectual Property Rights\n\nSection 1 Copyright and Related Rights\n\nArticle 9 Relationship with the Berne Convention",
            "output": [
                ("Article 8 Principles", 3),
                ("Part Two: Standards Concerning the Availability, Scope and Use of Intellectual Property Rights", 1),
                ("Section 1 Copyright and Related Rights", 2),
                ("Article 9 Relationship with the Berne Convention", 3)
            ]
        }
    ]
}
"""

    def __init__(self, language: str | None = "en"):
        super().__init__(language)

    @property
    def template_variables(self) -> list[str]:
        return ["input", "current_outline"]

    def parse_response(self, response: str, **kwargs):
        if isinstance(response, str):
            cleaned_data = response.strip("`python\n[] \n")
            cleaned_data = "[" + cleaned_data + "]"
            try:
                parsed_data = ast.literal_eval(cleaned_data)
            except Exception as e:
                raise ValueError("Cannot parse the returned string into a list") from e
            response = parsed_data

        if isinstance(response, dict) and "output" in response:
            response = response["output"]

        if isinstance(response, list) and all(
            isinstance(response[i], str) for i in range(0, len(response), 2)
        ):
            paired_list = []
            i = 0
            while i < len(response):
                title = response[i]
                if i + 1 < len(response):
                    raw_level = response[i + 1]
                    if not isinstance(raw_level, int):
                        raw_level_str = str(raw_level).strip()
                        level = (
                            int(raw_level_str)
                            if raw_level_str.isdigit()
                            else (paired_list[-1][1] if paired_list else 3)
                        )
                    else:
                        level = raw_level
                    paired_list.append((title, level))
                    i += 2
                else:
                    level = paired_list[-1][1] if paired_list else 3
                    paired_list.append((title, level))
                    i += 1
            return paired_list

        outline = kwargs.get("outline", [])
        for r in response:
            if isinstance(r, (list, tuple)):
                if not r:
                    continue
                if len(r) >= 2:
                    title, raw_level = r[0], r[1]
                else:
                    title = r[0]
                    raw_level = outline[-1][1] if outline else 3
                if not isinstance(raw_level, int):
                    raw_level_str = str(raw_level).strip()
                    level = (
                        int(raw_level_str)
                        if raw_level_str.isdigit()
                        else (outline[-1][1] if outline else 3)
                    )
                else:
                    level = raw_level
                outline.append((title, level))
            else:
                continue
        return outline
