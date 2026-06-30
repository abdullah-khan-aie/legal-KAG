import asyncio
from abc import ABC, abstractmethod

from kag.common.registry import Registrable


class GeneratorABC(Registrable, ABC):
    """Abstract base class for components that generate final answers from problem-solving context.

    Defines the interface for answer generation modules that synthesize solutions based on
    accumulated execution context from prior processing steps.
    """

    @abstractmethod
    def invoke(self, query, context, **kwargs):
        """Synchronous interface for generating final answer.

        Args:
            query: Original user query being addressed
            context: Execution context containing intermediate results
            **kwargs: Additional generation parameters

        Returns:
            Generated answer object

        Raises:
            NotImplementedError: If subclass doesn't implement this method
        """
        raise NotImplementedError("invoke not implemented yet.")

    async def ainvoke(self, query, context, **kwargs):
        """Asynchronous interface for answer generation.

        Converts the synchronous invoke() call to run in a separate thread using asyncio.

        Args:
            query: Original user query
            context: Execution context with intermediate results
            **kwargs: Additional parameters

        Returns:
            Asynchronously generated answer
        """
        return await asyncio.to_thread(lambda: self.invoke(query, context, **kwargs))
