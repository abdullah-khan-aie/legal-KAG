import json
from string import Template

from kag.interface import PromptABC
from kag.reasoner.client import ReasonerClient


@PromptABC.register("default_question_ner")
class QuestionNER(PromptABC):
    template_en = """
    {
        "instruction": "You are an expert in named entity recognition. Please extract entities and that match the schema definition from the input. Please respond in the format of a JSON string.You can refer to the example for extraction.",
        "schema": $schema,
        "output_format": "only output with json format, don't output other information",
        "example": [
            {
                "input": "Which magazine was started first, Arthur's Magazine or First for Women?",
                "output": [
                        {
                            "name": "First for Women",
                            "category": "Works"
                        },
                        {
                            "name": "Arthur's Magazine",
                            "category": "Works"
                        }
                    ]
            }
        ],
        "input": "$input"
    }    
        """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.schema = (
            ReasonerClient(
                project_id=self.kag_project_config.project_id,
                host_addr=self.kag_project_config.host_addr,
                namespace=self.kag_project_config.namespace,
            )
            .get_reason_schema()
            .keys()
        )
        self.template = Template(self.template).safe_substitute(schema=self.schema)

    @property
    def template_variables(self) -> list[str]:
        return ["input"]

    def parse_response(self, response: str, **kwargs):
        rsp = response
        if isinstance(rsp, str):
            rsp = json.loads(rsp)
        if isinstance(rsp, dict) and "output" in rsp:
            rsp = rsp["output"]
        if isinstance(rsp, dict) and "named_entities" in rsp:
            entities = rsp["named_entities"]
        else:
            entities = rsp

        return entities
