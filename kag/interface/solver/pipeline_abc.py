from kag.common.registry import Registrable


class SolverPipelineABC(Registrable):
    """Base class for solver pipelines.

    This abstract base class defines the interface for solver pipeline implementations.
    Subclasses must implement the `invoke` and `ainvoke` methods to provide concrete
    execution logic.
    """

    def __init__(self):
        """Initializes the solver pipeline base class."""
        super().__init__()

    def invoke(self, query, **kwargs):
        """Executes the solver pipeline synchronously.

        Args:
            query: Input query or data to be processed by the pipeline.
            **kwargs: Additional keyword arguments for pipeline execution.

        Raises:
            NotImplementedError: If the subclass does not implement this method.
        """
        raise NotImplementedError("invoke not implemented yet.")

    async def ainvoke(self, query, **kwargs):
        """Executes the solver pipeline asynchronously.

        Args:
            query: Input query or data to be processed by the pipeline.
            **kwargs: Additional keyword arguments for pipeline execution.

        Raises:
            NotImplementedError: If the subclass does not implement this method.
        """
        raise NotImplementedError("ainvoke not implemented yet.")
