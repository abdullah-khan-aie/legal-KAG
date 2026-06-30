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


@SolverPipelineABC.register("kag_static_pipeline")
class KAGStaticPipeline(SolverPipelineABC):
    """Plan all tasks up front, execute them, and synthesize a final answer.

    Generates a static task DAG, runs it in dependency-ordered parallel batches,
    and optionally retries planning until the answer is judged complete.
    """

    def __init__(
        self,
        planner: PlannerABC,
        executors: list[ExecutorABC],
        generator: GeneratorABC,
        max_iteration: int = 1,
    ):
        super().__init__()
        self.planner = planner
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
        if hasattr(self.planner, "check_require_rewrite") and self.planner.check_require_rewrite(
            task
        ):
            task.update_memory("origin_arguments", task.arguments)
            updated_args = await self.planner.query_rewrite(
                task, query=query, context=context, **kwargs
            )
            task.arguments.update(updated_args)
        executor = self.select_executor(task.executor)
        if executor:
            await executor.ainvoke(query, task, context, **kwargs)
        else:
            logger.warn(f"Executor not  found for task {task}")

    async def ainvoke(self, query, **kwargs):
        """Plan, execute, and answer the query, retrying until judged complete.

        Each attempt builds a task DAG, runs it in dependency-ordered parallel
        batches, and generates an answer; planning repeats up to the iteration
        limit while the answer is judged unfinished.

        Args:
            query: The user query to solve.

        Returns:
            The generated answer.
        """
        num_retry = self.max_iteration - 1
        finished = False
        while True:
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
            if num_retry > 0:
                if "unknown" in answer.lower():
                    finished = False
                else:
                    finished = await self.planner.finish_judger(query, answer)
            if not finished and self.max_iteration > 1:
                if num_retry <= 0:
                    print(
                        f"{red}Failed to answer quesion: {query}\nTasks:{task_info}\n{reset}\n{answer}"
                    )
                else:
                    num_retry -= 1
                    print(
                        f"{red}Retry to answer quesion: {query}\nTasks:{task_info}\n{reset}\n{answer}"
                    )
                    continue
            print(
                f"{green}Input Query: {query}\n\nTasks:\n\n{task_info}\n\nFinal Answer: {answer}\nGold Answer: {kwargs.get('gold')}{reset}"
            )
            return answer
