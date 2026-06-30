import json
from typing import ClassVar

from kag.interface import PromptABC, Task


@PromptABC.register("default_static_planning")
class DefaultStaticPlanningPrompt(PromptABC):
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
            "query": "Which movies have Jacky Cheung and Andy Lau starred in together?",
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
                {
                    "name": "Math",
                    "description": "Used to address users' math or computational problems.",
                    "parameters": {
                        "query": {
                            "type": "string",
                            "description": "The computable problem derived from the user's input question, retaining the essential information for the calculation target and dependencies.",
                            "optional": False,
                        }
                    },
                },
            ],
            "output": {
                "0": {
                    "executor": "Retriever",
                    "dependent_task_ids": [],
                    "arguments": {"query": "List of movies Jacky Cheung has starred in"},
                },
                "1": {
                    "executor": "Retriever",
                    "dependent_task_ids": [],
                    "arguments": {"query": "List of movies Andy Lau has starred in"},
                },
                "2": {
                    "executor": "Code",
                    "dependent_task_ids": ["0", "1"],
                    "arguments": {
                        "query": "Please write Python code to find the common elements in the following two lists:\nJacky Cheung movie list: {{0.output}}\nAndy Lau movie list: {{1.output}}"
                    },
                },
            },
        },
    }

    @property
    def template_variables(self) -> list[str]:
        return ["executors", "query"]

    def parse_response(self, response: str, **kwargs):
        if isinstance(response, str):
            try:
                response_json = json.loads(response)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Failed to decode LLM response as JSON: {e}. Response: {response}"
                )
        elif isinstance(response, dict):
            response_json = response  # If it's already a dict (e.g. from direct LLM client parsing)
        else:
            raise ValueError(
                f"LLM response is not a JSON string or a dictionary. Got type: {type(response)}. Response: {response}"
            )

        if not isinstance(response_json, dict):
            # This case might be redundant if json.loads already ensures a dict or list,
            # but good for safety if the initial response could be a non-dict JSON type.
            raise ValueError(
                f"Parsed LLM response should be a dict, but got {type(response_json)}. Response: {response_json}"
            )

        # Handle if the LLM wraps the DAG in an "output" key, as per original logic
        actual_dag_data = response_json.get("output", response_json)

        if not isinstance(actual_dag_data, dict):
            raise ValueError(
                f"The core plan data (after handling potential 'output' key) is not a dictionary. Got type: {type(actual_dag_data)}. Data: {actual_dag_data}"
            )

        try:
            return Task.create_tasks_from_dag(actual_dag_data)
        except (KeyError, TypeError) as e:
            error_message = (
                f"LLM response for static planning was malformed. Error: {e}. "
                f"Each task in the DAG dictionary must define 'executor', 'arguments', and 'dependent_task_ids'. "
                f"Problematic DAG data: {actual_dag_data}"
            )
            raise ValueError(error_message)
        except Exception as e:  # Catch any other unexpected errors from create_tasks_from_dag
            error_message = (
                f"An unexpected error occurred while creating tasks from DAG. Error: {e}. "
                f"Problematic DAG data: {actual_dag_data}"
            )
            raise ValueError(error_message)
