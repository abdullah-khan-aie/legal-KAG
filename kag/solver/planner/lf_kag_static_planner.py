import json

from kag.interface import LLMClient, PlannerABC, PromptABC, Task
from kag.interface.solver.planner_abc import format_task_dep_context


@PlannerABC.register("lf_kag_static_planner")
class KAGLFStaticPlanner(PlannerABC):
    """Plan a logical-form task DAG up front with the LLM, with query rewriting."""

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
            print(f"Failed to run finish_judger, info: {e}")
            import traceback

            traceback.print_exc()
            return True

    @staticmethod
    def check_require_rewrite(task: Task):
        """Return whether the task is flagged as needing query rewriting."""
        return task.arguments.get("is_need_rewrite", False)

    async def query_rewrite(self, task: Task, **kwargs):
        """Rewrite a task's query against its dependencies' results.

        Args:
            task: The task whose query should be rewritten.

        Returns:
            Updated task arguments carrying the rewritten query.
        """
        query = task.arguments["query"]
        tag_id = f"{query}_begin_task"
        deps_context = format_task_dep_context(task.parents)
        generate_context = {
            "target question": kwargs.get("query"),
            "history_qa": deps_context,
        }
        new_query = await self.llm.ainvoke(
            {
                "input": query,
                "content": json.dumps(generate_context, indent=2, ensure_ascii=False),
            },
            self.rewrite_prompt,
            segment_name=tag_id,
            tag_name="Rewrite query",
            with_json_parse=self.rewrite_prompt.is_json_format(),
            **kwargs,
        )
        logic_form_node = task.arguments.get("logic_form_node", None)
        if logic_form_node:
            logic_form_node.sub_query = new_query
            return {
                "rewrite_query": new_query,
                "origin_query": query,
                "query": new_query,
                "logic_form_node": logic_form_node,
            }
        return {"query": new_query}

    def invoke(self, query, **kwargs) -> list[Task]:
        """Generate the full task plan for the query with the LLM, retrying on error.

        Args:
            query: The user query to plan for.

        Keyword Args:
            executors: Available executors the plan may target.

        Returns:
            The planned tasks.
        """
        num_iteration = kwargs.get("num_iteration", 0)
        retry_num = 3
        while retry_num > 0:
            try:
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
            except Exception as e:
                retry_num -= 1
                if retry_num == 0:
                    raise e
        return None

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
