from kag.interface import PlannerABC, Task


@PlannerABC.register("mcp_planner")
class MCPPlanner(PlannerABC):
    """mcp planner that generates task plans"""

    def __init__(
        self,
        **kwargs,
    ):
        super().__init__(**kwargs)

    async def ainvoke(self, query, **kwargs) -> list[Task]:
        """Asynchronously generates task plan without LLM.

        Args:
            query: User query to generate plan for
            **kwargs: Additional parameters including:
                - executors (list): Available executors for task planning

        Returns:
            List[Task]: Generated task sequence
        """
        task = Task("mcp", arguments={"query": query})
        return [task]

    @staticmethod
    def check_require_rewrite(task: Task):
        return False
