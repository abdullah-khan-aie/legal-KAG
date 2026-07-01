import asyncio
import logging

from tenacity import retry, stop_after_attempt

from kag.interface import (
    Context,
    ExecutorABC,
    GeneratorABC,
    SolverPipelineABC,
    Task,
)

logger = logging.getLogger(__name__)


@SolverPipelineABC.register("index_pipeline")
class IndexPipeline(SolverPipelineABC):
    def __init__(
        self,
        executors: list[ExecutorABC],
        generator: GeneratorABC,
        max_iteration: int = 5,
    ):
        super().__init__()
        self.executors = executors
        self.generator = generator
        self.max_iteration = max_iteration

    def select_executor(self, executor_name: str):
        """Return the executor whose schema name matches, or None if absent."""
        for executor in self.executors:
            schema = executor.schema()
            if executor_name == schema["name"]:
                return executor
        return None

    @retry(stop=stop_after_attempt(3), reraise=True)
    async def planning(self, query, context, **kwargs):
        """Build the task plan, a single retrieval task for the query."""

        return [Task(executor="Retriever", arguments={"query": query})]

    @retry(stop=stop_after_attempt(3), reraise=True)
    async def execute_task(self, query, task, context, **kwargs):
        """Run a single task by dispatching it to its matching executor."""
        executor = self.select_executor(task.executor)
        if executor:
            await executor.ainvoke(query, task, context, **kwargs)
        else:
            logger.warning(f"Executor not  found for task {task}")

    async def ainvoke(self, query, **kwargs):
        """Run the full pipeline and return the generated answer.

        Plans the tasks, executes them in dependency-ordered parallel batches,
        and generates the final answer from the accumulated context.

        Args:
            query: The user query to solve.

        Returns:
            The generated answer.
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

        return answer
