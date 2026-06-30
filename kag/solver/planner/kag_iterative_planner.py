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


from kag.interface import Context, LLMClient, PlannerABC, PromptABC, Task


@PlannerABC.register("kag_iterative_planner")
class KAGIterativePlanner(PlannerABC):
    """Plan one task at a time with the LLM, conditioned on prior task results."""

    def __init__(self, llm: LLMClient, plan_prompt: PromptABC, **kwargs):
        super().__init__(**kwargs)
        self.llm = llm
        self.plan_prompt = plan_prompt

    @staticmethod
    def format_context(context: Context = None):
        """Format the context's task history into action/result entries."""
        formatted_context = []
        if context and isinstance(context, Context):
            for task in context.gen_task():
                formatted_context.append(
                    {
                        "action": {"name": task.executor, "argument": task.arguments},
                        "result": (
                            task.result.to_string()
                            if hasattr(task.result, "to_string")
                            else task.result
                        ),
                    }
                )
        return formatted_context

    def invoke(self, query, **kwargs) -> list[Task]:
        """Generate the next task for the query with the LLM.

        Args:
            query: The user query to plan for.

        Keyword Args:
            context: Execution context with prior task results.
            executors: Available executors the plan may target.

        Returns:
            The planned tasks.
        """
        num_iteration = kwargs.get("num_iteration", 0)
        return self.llm.invoke(
            {
                "query": query,
                "context": self.format_context(kwargs.get("context")),
                "executors": kwargs.get("executors", []),
            },
            self.plan_prompt,
            segment_name="thinker",
            tag_name=f"Iterative planning {num_iteration}",
            **kwargs,
        )

    def is_static(self):
        return False

    async def ainvoke(self, query, **kwargs) -> list[Task]:
        """Asynchronously generate the next task for the query with the LLM.

        Args:
            query: The user query to plan for.

        Keyword Args:
            context: Execution context with prior task results.
            executors: Available executors the plan may target.

        Returns:
            The planned tasks.
        """
        num_iteration = kwargs.get("num_iteration", 0)
        return await self.llm.ainvoke(
            {
                "query": query,
                "context": self.format_context(kwargs.get("context")),
                "executors": kwargs.get("executors", []),
            },
            self.plan_prompt,
            segment_name="thinker",
            tag_name=f"Iterative planning {num_iteration}",
            **kwargs,
        )
