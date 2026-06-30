import logging
import re

from kag.interface import LLMClient, PlannerABC, PromptABC, Task


@PlannerABC.register("kag_static_planner")
class KAGStaticPlanner(PlannerABC):
    """Plan the full task DAG up front with the LLM, with query rewriting support."""

    def __init__(
        self,
        llm: LLMClient,
        plan_prompt: PromptABC,
        rewrite_prompt: PromptABC,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.llm = llm
        self.plan_prompt = plan_prompt
        self.rewrite_prompt = rewrite_prompt

    @staticmethod
    def format_context(task: Task):
        """Map each parent task's id to its query and result output."""
        formatted_context = {}
        for parent_task in task.parents:
            formatted_context[parent_task.id] = {
                "query": parent_task.arguments["query"],
                "output": str(parent_task.result),
            }
        return formatted_context

    @staticmethod
    def check_require_rewrite(task: Task):
        """Return whether the task references a dependency output (e.g. ``{{1.output}}``)."""
        query = task.arguments
        pattern = r"\{\{\d+\.output\}\}"
        return bool(re.search(pattern, str(query)))

    async def finish_judger(self, query: str, answer: str):
        finish_prompt = f"""
        # Task
        The answer is a response to a question. Please determine whether the content of this answer is invalid, such as  "UNKNOWN", "I don't know" or "Insufficient Information."  \n
        If the answer is invalid, return "Yes", otherwise, return "No".\n
        You output should only be "Yes" or "No".\n
        
        # Answer\n
        {answer}
        """
        try:
            response = await self.llm.acall(prompt=finish_prompt)
            if response.strip().lower() == "yes":
                return False
            return True
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.warning(
                f"LLM call failed in finish_judger for query '{query}'. Error: {e}",
                exc_info=True,
            )
            return False  # Treat as potentially bad answer

    async def query_rewrite(self, task: Task, **kwargs):
        """Rewrite the task's query, resolving references to parent results.

        Args:
            task: The task whose query should be rewritten.

        Returns:
            The rewritten query.
        """
        query = task.arguments
        context = self.format_context(task)
        new_query = await self.llm.ainvoke(
            {
                "input": query,
                "context": context,
            },
            self.rewrite_prompt,
            segment_name="thinker",
            tag_name="Rewrite query",
            with_json_parse=self.rewrite_prompt.is_json_format(),
            **kwargs,
        )
        return new_query

    def invoke(self, query, **kwargs) -> list[Task]:
        """Generate the full task plan for the query with the LLM.

        Args:
            query: The user query to plan for.

        Keyword Args:
            executors: Available executors the plan may target.

        Returns:
            The planned tasks.
        """
        num_iteration = kwargs.get("num_iteration", 0)

        return self.llm.invoke(
            {
                "query": query,
                "executors": kwargs.get("executors", []),
            },
            self.plan_prompt,
            with_json_parse=self.plan_prompt.is_json_format(),
            segment_name="thinker",
            tag_name=f"Static planning {num_iteration}",
            **kwargs,
        )

    async def ainvoke(self, query, **kwargs) -> list[Task]:
        """Asynchronously generate the full task plan for the query with the LLM.

        Args:
            query: The user query to plan for.

        Keyword Args:
            executors: Available executors the plan may target.

        Returns:
            The planned tasks.
        """
        num_iteration = kwargs.get("num_iteration", 0)
        return await self.llm.ainvoke(
            {
                "query": query,
                "executors": kwargs.get("executors", []),
            },
            self.plan_prompt,
            with_json_parse=self.plan_prompt.is_json_format(),
            segment_name="thinker",
            tag_name=f"Static planning {num_iteration}",
            **kwargs,
        )
