# Copyright 2023 OpenSPG Authors
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except
# in compliance with the License. You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under the License
# is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
# or implied.

import json
from typing import ClassVar

from kag.interface import PromptABC, Task


@PromptABC.register("default_retriever_static_planning")
class RetrieverStaticPlanningPrompt(PromptABC):
    template_en: ClassVar[dict] = {
        "instruction": """

You are a problem-solving planner. Your task is to analyze complex problems provided by users and, through your analysis and reasoning, provide specific step-by-step plans for solving the problem using available tools. The plan should be represented as a Directed Acyclic Graph (DAG). Note that you do not need to answer the question directly but instead produce the steps required to answer the question. The user's question is provided in the query field, and the available tools are listed in the executors field.

Your reasoning should follow these steps:
1. Analyze the request to understand the scope of the task.
2. Break down the original complex problem into several finest-grained atomic problem sets and define their dependencies in DAG format.
3. Use the tools defined in executors to create clear and actionable plans to drive the task forward and make substantial progress.

Note:
1. Please return your planning result in JSON format, following the example in the output field of the example section.
""",
        "example": {
            "query": "Which year was Zhou Xingchi's first movie released?",
            "executors": [
                {
                    "name": "Retriever",
                    "description": "Retrieve relevant knowledge from the local knowledge base.",
                    "parameters": {
                        "query": {
                            "type": "string",
                            "description": "User-provided query for retrieval.",
                            "optional": False,
                        },
                    },
                },
            ],
            "output": {
                "0": {
                    "executor": "Retriever",
                    "dependent_task_ids": [],
                    "arguments": {"query": "What was Zhou Xingchi's first movie?"},
                },
                "1": {
                    "executor": "Retriever",
                    "dependent_task_ids": ["0"],
                    "arguments": {"query": "Which year was {{0.output}} released?"},
                },
            },
        },
    }

    @property
    def template_variables(self) -> list[str]:
        return ["executors", "query"]

    def parse_response(self, response: str, **kwargs):
        if isinstance(response, str):
            response = json.loads(response)
        if not isinstance(response, dict):
            raise ValueError(f"response should be a dict, but got {type(response)}")
        if "output" in response:
            response = response["output"]
        return Task.create_tasks_from_dag(response)
