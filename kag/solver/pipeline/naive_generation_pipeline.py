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
import logging

from kag.interface import (
    Context,
    GeneratorABC,
    SolverPipelineABC,
)

logger = logging.getLogger(__name__)


@SolverPipelineABC.register("naive_generation_pipeline")
class NaiveGenerationPipeline(SolverPipelineABC):
    """Answer queries by generating directly with the LLM, without retrieval."""

    def __init__(
        self,
        generator: GeneratorABC,
    ):
        super().__init__()
        self.generator = generator

    async def ainvoke(self, query, **kwargs):
        """Generate an answer for the query directly with the generator.

        Args:
            query: The user query to solve.

        Returns:
            The generated answer, or ``"UNKNOWN"`` when none could be produced.
        """
        context: Context = Context()
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
