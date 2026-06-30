from kag.interface import PlannerABC, Task


@PlannerABC.register("mcp_planner")
class MCPPlanner(PlannerABC):
    """Planner that emits a single MCP task for the query, without an LLM."""

    def __init__(
        self,
        **kwargs,
    ):
        super().__init__(**kwargs)

    async def ainvoke(self, query, **kwargs) -> list[Task]:
        """Build the task plan, a single MCP task for the query."""
        task = Task("mcp", arguments={"query": query})
        return [task]

    @staticmethod
    def check_require_rewrite(task: Task):
        return False
