import json
import logging

from kag.interface import PromptABC


@PromptABC.register("table_context")
class TableContextPrompt(PromptABC):
    """
    extract table context
    """


    template_en = """
# Your Task
Based on the provided table and its context, summarize the table name, table description, and table keywords.
# Requirements
The table name should be easy to understand and provide complete information.
# Output Format
In JSON format, for example:
```json
{
  "table_desc": "Description of the table content",
  "keywords": [
    "List of keywords"
  ],
  "table_name": "Table name"
}
```
# Table and it's Context Information
$input
# Your Answer
""".strip()

    @property
    def template_variables(self) -> list[str]:
        return ["input"]

    def parse_response(self, response: str, **kwargs):
        rsp = response
        if isinstance(rsp, str):
            try:
                rsp = json.loads(rsp)
            except json.decoder.JSONDecodeError as e:
                logging.exception("json_str=%s", rsp)
                raise e
        if isinstance(rsp, dict) and "output" in rsp:
            rsp = rsp["output"]
        return rsp
