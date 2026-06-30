from tenacity import retry, stop_after_attempt

from kag.interface import (
    Context,
    ExecutorABC,
    GeneratorABC,
    PlannerABC,
    SolverPipelineABC,
)


class MaxIterationsReachedError(RuntimeError):
    pass


@SolverPipelineABC.register("kag_iterative_pipeline")
class KAGIterativePipeline(SolverPipelineABC):
    """Iterative problem-solving pipeline that decomposes and analyzes problems step-by-step.

    This pipeline coordinates planners, executors, and generators to solve problems through
    repeated planning and execution cycles until completion or iteration limit is reached.
    """

    def __init__(
        self,
        planner: PlannerABC,
        executors: list[ExecutorABC],
        generator: GeneratorABC,
        max_iteration: int = 5,
    ):
        """Initialize the iterative pipeline.

        Args:
            planner: Component responsible for generating execution plans
            executors: List of available executor components for task execution
            generator: Component that generates final answers from context
            max_iteration: Maximum number of allowed execution cycles (default: 5)
        """
        super().__init__()
        self.planner = planner
        self.executors = executors
        self.generator = generator
        self.max_iteration = max_iteration
        # append a finish executor to indicate task is finished.
        self.finish_executor = ExecutorABC.from_config({"type": "finish_executor"})
        self.executors.append(self.finish_executor)

    def select_executor(self, executor_name: str):
        """Return the executor whose schema name matches, or None if absent."""
        for executor in self.executors:
            schema = executor.schema()
            if executor_name == schema["name"]:
                return executor
        return None

    @retry(stop=stop_after_attempt(3), reraise=True)
    async def planning(self, query, context, **kwargs):
        """Plan the next task and resolve its executor.

        Args:
            query: The user query being processed.
            context: Current execution context with prior tasks.

        Returns:
            The planned task paired with its executor.

        Raises:
            ValueError: If no available executor matches the planned task.
        """
        task = await self.planner.ainvoke(
            query,
            context=context,
            executors=[x.schema() for x in self.executors],
            **kwargs,
        )
        if isinstance(task, list):
            task = task[0]
        executor = self.select_executor(task.executor)
        if not executor:
            raise ValueError(f"Executor {task.executor} not in acceptable executors.")
        return task, executor

    async def ainvoke(self, query, **kwargs):
        """Iteratively plan and execute tasks until finished, then answer.

        Args:
            query: The user query to solve.

        Returns:
            The generated answer from the final context.

        Raises:
            MaxIterationsReachedError: If the iteration limit is hit before the
                pipeline signals completion.
        """
        num_iteration = 0
        context: Context = Context()
        finished_by_executor = False
        while num_iteration < self.max_iteration:
            num_iteration += 1
            task, executor = await self.planning(
                query, context, num_iteration=num_iteration, **kwargs
            )

            if executor == self.finish_executor:
                context.append_task(task)
                finished_by_executor = True
                break

            await executor.ainvoke(query, task, context, **kwargs)
            # Add task to context only after successful execution
            context.append_task(task)

        if not finished_by_executor:
            raise MaxIterationsReachedError(
                f"Pipeline reached max_iteration ({self.max_iteration}) "
                f"without finishing for query: {query}"
            )

        answer = await self.generator.ainvoke(query, context, **kwargs)
        return answer
