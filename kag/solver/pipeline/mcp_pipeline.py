import asyncio
import logging

from tenacity import retry, stop_after_attempt

from kag.interface import (
    Context,
    ExecutorABC,
    GeneratorABC,
    PlannerABC,
    SolverPipelineABC,
)

logger = logging.getLogger(__name__)


@SolverPipelineABC.register("mcp_pipeline")
class MCPPipeline(SolverPipelineABC):
    def __init__(
        self,
        planner: PlannerABC,
        executors: list[ExecutorABC],
        generator: GeneratorABC,
        max_iteration: int = 5,
    ):
        super().__init__()
        self.planner = planner
        self.executors = executors
        self.generator = generator
        self.max_iteration = max_iteration

    def select_mcp_server(self, mcp_server_name: str):
        """Return the MCP server entry matching the name, or None if absent."""
        mcp_schema_data = self.executor.schema()

        for server in mcp_schema_data.get("available_servers", []):
            if server["name"] == mcp_server_name:
                return {"name": server["name"], "desc": server["desc"]}
        return None

    @retry(stop=stop_after_attempt(3), reraise=True)
    async def planning(self, query, context, **kwargs):
        """Plan the task DAG for the query via the planner.

        Args:
            query: The user query to plan for.
            context: Execution context holding prior task results.

        Returns:
            The planned tasks forming the execution DAG.
        """
        tasks = await self.planner.ainvoke(
            query,
            context=context,
            executors=[x.schema() for x in self.executors],
            **kwargs,
        )
        return tasks

    @retry(stop=stop_after_attempt(3), reraise=True)
    async def execute_task(self, query, task, context, **kwargs):
        """Run a single task, rewriting its arguments first when required.

        Args:
            query: The user query being processed.
            task: The task to execute.
            context: Execution context for dependency resolution.
        """
        if self.planner.check_require_rewrite(task):
            task.update_memory("origin_arguments", task.arguments)
            task.arguments = await self.planner.query_rewrite(task, **kwargs)
        mcp_server = self.select_mcp_server(task.executor)
        if mcp_server:
            await self.executors[0].ainvoke(query, task, context, **kwargs)
        else:
            logger.warning(f"Executor not  found for task {task}")

    async def ainvoke(self, query, **kwargs):
        """Plan, execute the task DAG, and return the generated answer.

        Args:
            query: The user query to solve.

        Returns:
            The generated answer, or ``"UNKNOWN"`` when none could be produced.
        """
        context: Context = Context()
        tasks = await self.planning(query, context, **kwargs)

        for task in tasks:
            context.add_task(task)

        for task_group in context.gen_task(group=True):
            await asyncio.gather(
                *[
                    asyncio.create_task(self.execute_task(query, task, context, **kwargs))
                    for task in task_group
                ]
            )

        answer = await self.generator.ainvoke(query, context, **kwargs)
        from kag.common.utils import green, red, reset

        task_info = []
        for task in context.gen_task(group=False):
            task_info.append(
                {
                    "task": task.arguments,
                    "memory": task.memory,
                    "result": task.result,
                }
            )
        if answer is None:
            print(f"{red}Failed to answer quesion: {query}\nTasks:{task_info}\n{reset}")
            return "UNKNOWN"
        print(
            f"{green}Input Query: {query}\n\nTasks:\n\n{task_info}\n\nFinal Answer: {answer}\nGold Answer: {kwargs.get('gold')}{reset}"
        )
        return answer
