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


@SolverPipelineABC.register("naive_rag_pipeline")
class NaiveRAGPipeline(SolverPipelineABC):
    """Answer queries with naive RAG: retrieve relevant chunks, then generate."""

    def __init__(
        self,
        executors: list[ExecutorABC],
        generator: GeneratorABC,
    ):
        super().__init__()
        self.executors = executors
        self.generator = generator

    def select_executor(self, executor_name: str):
        """Return the executor whose schema name matches, or None if absent."""
        for executor in self.executors:
            schema = executor.schema()
            if executor_name == schema["name"]:
                return executor
        return None

    @retry(stop=stop_after_attempt(3), reraise=True)
    async def planning(self, query, context, **kwargs):
        """Build the task plan, a single chunk-retrieval task for the query."""
        tasks_dep = {}
        tasks_dep[0] = {
            "executor": "ChunkRetriever",
            "dependent_task_ids": [],
            "arguments": {"query": query},
        }
        return Task.create_tasks_from_dag(tasks_dep)

    @retry(stop=stop_after_attempt(3), reraise=True)
    async def execute_task(self, query, task, context, **kwargs):
        """Run a single task by dispatching it to its matching executor."""
        executor = self.select_executor(task.executor)
        if executor:
            await executor.ainvoke(query, task, context, **kwargs)
        else:
            logger.warn(f"Executor not  found for task {task}")

    async def ainvoke(self, query, **kwargs):
        """Retrieve chunks then generate and return the answer for the query.

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
