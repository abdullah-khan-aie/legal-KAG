#

import json
import logging

from kag.interface import PromptABC

logger = logging.getLogger(__name__)


@PromptABC.register("analyze_table")
class AnalyzeTablePrompt(PromptABC):
    template_en: str = """You are an expert in knowledge graph extraction. Based on the schema defined by the constraint, extract all entities and their attributes from the input. Return NAN for attributes not explicitly mentioned in the input. Output the results in standard JSON format, as a list."""

    def build_prompt(self, variables) -> str:
        return json.dumps(
            {
                "instruction": self.template,
                "table": variables.get("table", ""),
            },
            ensure_ascii=False,
        )

    def parse_response(self, response: str, **kwargs):
        return response
