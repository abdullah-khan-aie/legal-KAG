import logging
import os

from kag.common.conf import KAGConfigAccessor, KAGConstants
from kag.interface import Context, ExecutorABC, LLMClient, PromptABC
from kag.solver.executor.mcp.mcp_client import MCPClient

logger = logging.getLogger()


@ExecutorABC.register("mcp_executor")
class McpExecutor(ExecutorABC):
    def __init__(
        self,
        store_path: str,
        name: str,
        description: str,
        llm: LLMClient,
        prompt: PromptABC = None,
        env: dict | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.name = name
        self.description = description
        self.mcp_file_path = self.download_data(store_path)
        self.prompt = prompt
        self.env = dict(env) if env else {}
        self.llm = llm
        self.mcp_client = MCPClient(self.llm, self.prompt)
        task_id = kwargs.get(KAGConstants.KAG_QA_TASK_CONFIG_KEY, None)
        kag_config = KAGConfigAccessor.get_config(task_id)
        self.kag_project_config = kag_config.global_config

    def download_data(self, data: str, **kwargs):
        """Resolve the MCP server source to a local path.

        Downloads the resource when ``input`` is an HTTP(S) URL; otherwise
        returns the input unchanged.

        Args:
            data: A URL or local path identifying the MCP server script.

        Returns:
            The local file path of the downloaded resource, or the original
            input when it is not a URL.
        """
        if data.startswith("http://") or data.startswith("https://"):
            from kag.common.utils import download_from_http

            local_file_path = os.path.join(self.kag_project_config.ckpt_dir, "mcp_service")
            if not os.path.exists(local_file_path):
                os.makedirs(local_file_path)
            from urllib.parse import urlparse

            parsed_url = urlparse(data)
            local_file = os.path.join(local_file_path, os.path.basename(parsed_url.path))

            local_file = download_from_http(data, local_file)
            return local_file
        return data

    async def ainvoke(self, query, task, context: Context, **kwargs):
        task_query = task.arguments["query"]
        try:
            await self.mcp_client.connect_to_server(self.mcp_file_path, self.env)
        except Exception as e:
            await self.mcp_client.cleanup()
            logger.error(f"Failed to connect to server: {e}")
        response = await self.mcp_client.process_query(task_query)
        task.update_result(response)
        return response


def schema(self, func_name: str = None) -> dict:
    """Return the executor's function-calling schema.

    Returns:
        The schema describing this executor in OpenAI function-call format.
    """
    return {
        "name": self.name,
        "description": self.description,
        "parameters": {
            "query": {
                "type": "string",
                "description": "User-provided query for retrieval.",
                "optional": False,
            },
        },
    }
