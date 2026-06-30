import json
import logging

from kag.interface import PromptABC


@PromptABC.register("table_row_col_summary")
class TableRowColSummaryPrompt(PromptABC):
    """
    矩阵型表格索引信息提取
    """


    template_en = """
# Your Task
Based on the provided table and contextual information, generate a summary for each row and column of the table.
# Instructions
1. For each row in the table, first determine whether the row belongs to the header or the data rows, then summarize the content of that row.
2. For each column in the table, determine whether the column serves as an index column or a data column, then summarize the content of that column.
3. The summaries must not repeat the exact content or data from the rows or columns.
4. Ensure that readers can fully understand the information conveyed by the rows and columns through the summaries alone.
# Output Format
JSON format example:
```json
{
  "rows": [
    {"index":0, "type": "header", "summary": "Summary of the header row"},
    {"index":1, "type": "header", "summary": "Summary of the second header row (multi-level header)"},
    {"index":3, "type": "data", "summary": "Summary of the first data row"}
  ],
  "columns": [
    {"index":0, "type": "index", "summary": "Summary of the index column"},
    {"index":1, "type": "index", "summary": "Summary of the second index column (multi-index structure)"},
    {"index":2, "type": "data", "summary": "Summary of the first data column"}
  ]
}
```
# Input Table
$input
# Your JSON Output
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
