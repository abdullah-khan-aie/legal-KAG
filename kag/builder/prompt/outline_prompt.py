# Vendored from kag/builder/prompt/outline_prompt.py (openspg-kag 0.8.0, Apache-2.0).
# VERBATIM (template_zh/template_en, examples, parse_response). Only change:
#   `from kag.interface import PromptABC` -> local interface import.

import ast

from kag_extracted.interface import PromptABC


@PromptABC.register("outline")
class OutlinePrompt(PromptABC):
    template_zh = """
{
    "instruction": "\nGiven a text content, please extract the titles and return them as a list. Each title should include the following information:\n- Title text\n- Title level (e.g., 1 for first level, 2 for second level, etc.)\n\nAssume titles follow these rules:\n1. Titles usually contain numbers. Since our text might be OCR-generated from images, titles may be hidden within paragraphs. Try to identify these numbered titles hidden in paragraphs.\n2. Title levels can be inferred through:\n   - Level 1: Usually document-level content.\n   - Level 2: Usually chapter-level content, with concise descriptions, sometimes starting with \"Part X\", \"Chapter X\", etc.\n   - Level 3 and below: Usually paragraph or detail-level titles, may include numerical prefixes (like \"1.\" or \"1.1\") or longer specific descriptions (like \"1.1 Subtitle\" or \"Section 1 Overview\").\n3. Title levels can also be determined by context:\n   - If the text between two titles is very short, the latter title might be of higher or same level.\n   - Consecutively numbered titles (like \"Article 1\", \"Article 2\") are usually of the same level.\n   - Title hierarchy is often determined by number levels, e.g., \"1\", \"1.1\", \"1.1.1\" are levels 1, 2, 3 respectively.\n   - Titles containing keywords like \"Part\", \"Chapter\", \"Section\", \"Article\" with moderate length (5-20 characters) often have higher levels than longer or shorter titles.\n4. Ignore the following titles:\n   - Pure numbers or titles consisting only of numbers and punctuation (e.g., \"1.\", \"2.1\").\n   - Repeated titles (e.g., headers/footers misidentified as titles).\n5. If content cannot be clearly identified as a title or doesn't match these rules, ignore it.\n\nPlease return a list of titles with their corresponding levels in the following format:\n[\n    (\"Title text 1\", 1),\n    (\"Title text 2\", 2),\n    (\"Title text 3\", 3),\n    ...\n]. I will also provide the previously extracted outline as current_outlines, and you need to judge the granularity and corresponding levels of title extraction based on the current outline.",
    "input": "$input",
    "current_outline:": "$current_outline",
    "example": [
        {
            "input": "Article 8 Principles\n\n1. In formulating or amending their laws and regulations, Members may adopt measures necessary to protect public health and nutrition, and to promote the public interest in sectors of vital importance to their socio-economic and technological development, provided that such measures are consistent with the provisions of this Agreement.\n\n2. Appropriate measures, provided that they are consistent with the provisions of this Agreement, may be needed to prevent the abuse of intellectual property rights by right holders or the resort to practices which unreasonably restrain trade or adversely affect the international transfer of technology.\n\nPart Two Standards Concerning the Availability, Scope and Use of Intellectual Property Rights\n\nSection 1 Copyright and Related Rights\n\nArticle 9 Relationship with the Berne Convention",
            "output": [
                ("Article 8 Principles",3),
                ("Part Two Standards Concerning the Availability, Scope and Use of Intellectual Property Rights",1),
                ("Section 1 Copyright and Related Rights",2),
                ("Article 9 Relationship with the Berne Convention",3)
            ]
        },
        {
            "input": "Article 16 Grant of Rights\n\n1. The owner of a registered trademark shall have the exclusive right to prevent all third parties not having the owner's consent from using in the course of trade identical or similar signs for goods or services which are identical or similar to those in respect of which the trademark is registered where such use would result in a likelihood of confusion. In case of the use of an identical sign for identical goods or services, a likelihood of confusion shall be presumed. The rights described above shall not prejudice any existing prior rights, nor shall they affect the possibility of Members making rights available on the basis of use.\n\n2. Article 6bis of the Paris Convention (1967) shall apply, mutatis mutandis, to services. In determining whether a trademark is well-known, Members shall take account of the knowledge of the trademark in the relevant sector of the public, including knowledge in the Member concerned obtained as a result of the promotion of the trademark.\n\n3. Article 6bis of the Paris Convention (1967) shall apply, mutatis mutandis, to goods or services which are not similar to those in respect of which a trademark is registered, provided that use of that trademark in relation to those goods or services would indicate a connection between those goods or services and the owner of the registered trademark, and provided that the interests of the owner of the registered trademark are likely to be damaged by such use.\n\nArticle 17 Exceptions\n ",
            "output": [
                ("Article 16 Grant of Rights",3),
                ("Article 17 Exceptions",3)
            ]
        },
        {
            "input": "by doing so.\n\n(4) such use shall be non-exclusive;\n\n(5) such use shall be non-assignable, except with that part of the enterprise or goodwill which enjoys such use;\n\n(6) any such use shall be authorized predominantly for the supply of the domestic market of the Member authorizing such use;\n\n(7) authorization for such use shall be liable, subject to adequate protection of the legitimate interests of the persons so authorized, to be terminated if and when the circumstances which led to it cease to exist and are unlikely to recur; the competent authority shall have the authority to review, upon motivated request, the continued existence of these circumstances;\n\n(8) the right holder shall be paid adequate remuneration in the circumstances of each case, taking into account the economic value of the authorization;\n\n(9) the legal validity of any decision relating to the authorization of such use shall be subject to judicial review or other independent review by a distinct higher authority in that Member;\n\n(10) any decision relating to the remuneration provided in respect of such use shall be subject to judicial review or other independent review by a distinct higher authority in that Member.\n",
            "output": []
        }
    ]
}
"""

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
        },
        {
            "input": "Article 16 Grant of Rights\n\n1. Owners of registered trademarks...\n\nArticle 17 Exceptions",
            "output": [
                ("Article 16 Grant of Rights", 3),
                ("Article 17 Exceptions", 3)
            ]
        },
        {
            "input": "by doing so.\n\n(4) The use of this category should be non-exclusive...",
            "output": []
        }
    ]
}
"""

    def __init__(self, language: str | None = "zh"):
        super().__init__(language)

    @property
    def template_variables(self) -> list[str]:
        return ["input", "current_outline"]

    def parse_response(self, response: str, **kwargs):
        # if the result is a string, strip Markdown syntax then use ast.literal_eval to convert to a list
        if isinstance(response, str):
            cleaned_data = response.strip(
                "`python\n[] \n"
            )  # strip Markdown syntax and extra whitespace
            cleaned_data = "[" + cleaned_data + "]"  # restore to list format
            try:
                parsed_data = ast.literal_eval(cleaned_data)
            except Exception as e:
                raise ValueError("unable to parse the returned string into a list") from e
            response = parsed_data

        # if the result is a dict containing an "output" key, use that key's value
        if isinstance(response, dict) and "output" in response:
            response = response["output"]

        # if response is a flat list (even indices are strings), convert to a list of (title, level) tuples
        if isinstance(response, list) and all(
            isinstance(response[i], str) for i in range(0, len(response), 2)
        ):
            paired_list = []
            i = 0
            while i < len(response):
                title = response[i]
                if i + 1 < len(response):
                    raw_level = response[i + 1]
                    # if raw_level is not an integer, try to convert it
                    if not isinstance(raw_level, int):
                        raw_level_str = str(raw_level).strip()
                        if raw_level_str.isdigit():
                            level = int(raw_level_str)
                        else:
                            level = paired_list[-1][1] if paired_list else 3
                    else:
                        level = raw_level
                    paired_list.append((title, level))
                    i += 2
                else:
                    level = paired_list[-1][1] if paired_list else 3
                    paired_list.append((title, level))
                    i += 1
            return paired_list

        # if the result is not a flat list but already a tuple-like list, handle potential unpacking issues
        outline = kwargs.get("outline", [])
        for r in response:
            # if r is an empty list or tuple, skip it
            if isinstance(r, (list, tuple)):
                if not r:
                    continue  # skip empty lists directly
                # if the tuple has more than two elements, take only the first two (ignore the rest)
                if len(r) >= 2:
                    title, raw_level = r[0], r[1]
                else:
                    title = r[0]
                    raw_level = outline[-1][1] if outline else 3
                # if raw_level is not an integer, try to convert it
                if not isinstance(raw_level, int):
                    raw_level_str = str(raw_level).strip()
                    if raw_level_str.isdigit():
                        level = int(raw_level_str)
                    else:
                        level = outline[-1][1] if outline else 3
                else:
                    level = raw_level
                outline.append((title, level))
            else:
                # skip elements that are not lists or tuples
                continue

        return outline
