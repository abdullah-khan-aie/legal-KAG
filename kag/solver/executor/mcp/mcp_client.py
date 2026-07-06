from __future__ import annotations

import asyncio
import json
import logging
import sys
from contextlib import AsyncExitStack
from typing import TYPE_CHECKING

from kag.interface import LLMClient, PromptABC

if TYPE_CHECKING:  # annotations only; the real import is lazy (see connect_to_server)
    from mcp import ClientSession

logger = logging.getLogger(__name__)


class MCPClient:
    def __init__(self, llm: LLMClient, prompt: PromptABC = None):
        """Initialize the MCP client.

        Args:
            llm: Language model client used for tool-call interactions.
            prompt: Prompt used to build tool-call messages; defaults to the
                ``default_mcp_tool_call`` configuration when omitted.
        """
        self.llm = llm
        self.prompt = prompt or PromptABC.from_config({"type": "default_mcp_tool_call"})
        self._cleanup_lock: asyncio.Lock = asyncio.Lock()
        self.session: ClientSession | None = None
        self.exit_stack = AsyncExitStack()

    async def connect_to_server(self, server_script_path: str, env: dict):
        """Connect to an MCP server and initialize a communication session.

        Starts the server script, opens a session, and lists its available tools.

        Args:
            server_script_path: Path to the server script (``.py`` or ``.js``).
            env: Environment variables passed to the server process.

        Raises:
            ValueError: If the script is not a Python or JavaScript file.
        """
        # Imported lazily: the local ``kag/solver/executor/mcp`` package shadows
        # the installed ``mcp`` SDK during component registration (the registry
        # walk imports this folder as top-level ``mcp``). Importing the SDK at
        # module top level would break that walk. The MCP executor is only used
        # by the optional ``mcp`` pipeline, so import the SDK here, on use.
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        is_python = server_script_path.endswith(".py")
        is_js = server_script_path.endswith(".js")
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")

        command = sys.executable if is_python else "node"
        server_params = StdioServerParameters(command=command, args=[server_script_path], env=env)

        try:
            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
            self.read, self.write = stdio_transport
            session = await self.exit_stack.enter_async_context(
                ClientSession(self.read, self.write)
            )
            await session.initialize()
            self.session = session
        except Exception as e:
            logging.error(f"Error initializing server: {e}")
            await self.cleanup()
            raise

        tools = await self.list_tools()
        print("\nConnected to server with tools:", [tool.name for tool in tools])

    async def list_tools(self):
        """List the tools exposed by the connected server.

        Returns:
            The tools advertised by the server.

        Raises:
            RuntimeError: If the server session is not initialized.
        """
        if not self.session:
            raise RuntimeError("Server not initialized")

        tools_response = await self.session.list_tools()
        tools = tools_response.tools
        return tools

    async def process_query(self, query: str) -> str:
        """Answer a query by letting the LLM call the server's tools.

        Builds the prompt, exposes the server tools to the LLM, executes any
        requested tool calls, and feeds their results back for a final response.

        Args:
            query: The user query to answer.

        Returns:
            The LLM's final response after any tool interactions.
        """
        messages = self.prompt.build_prompt(query)
        response = await self.session.list_tools()
        available_tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema,
                },
            }
            for tool in response.tools
        ]
        stream = None
        if hasattr(self.llm, "stream"):
            stream = self.llm.stream
            self.llm.stream = False
        response = await self.llm.acall(messages=messages, prompt="", tools=available_tools)
        if hasattr(self.llm, "stream"):
            self.llm.stream = stream
        print(f"responses = {response}")
        if not isinstance(response, str) and response.tool_calls:
            tool_calls_message = response.model_dump()
            messages.append(tool_calls_message)
            for tool_call in response.tool_calls:
                tool_call = tool_call.dict()
                tool_call_id = tool_call.get("id", None)
                tool_name = tool_call["function"]["name"]
                tool_args = json.loads(tool_call["function"]["arguments"])
                result = await self.session.call_tool(tool_name, tool_args)
                print(f"result = {result}")
                if tool_call_id:
                    messages.append(
                        {
                            "role": "tool",
                            "content": result.content[0].text,
                            "tool_call_id": tool_call["id"],
                        }
                    )
                else:
                    messages.append(
                        {
                            "role": "tool",
                            "content": result.content[0].text,
                        }
                    )
            final_response = await self.llm.acall(messages=messages)
            return final_response
        else:
            return response

    async def cleanup(self) -> None:
        """Clean up server resources."""
        async with self._cleanup_lock:
            try:
                await self.exit_stack.aclose()
                self.session = None
                self.stdio_context = None
            except Exception as e:
                logging.error(f"Error during cleanup of server: {e}")

    async def __aenter__(self):
        """Enter the async context manager."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the async context manager."""
        await self.cleanup()
