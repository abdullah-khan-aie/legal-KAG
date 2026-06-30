from kag.interface import PromptABC


@PromptABC.register("default_mcp_tool_call")
class MCPToolCallPrompt(PromptABC):
    template_en = """In this environment you have access to a set of tools you can use to answer the user's questions.
You can invoke a function by writing a <tool_calls> block like the following:
<tool_calls>
<tool_call id="call_1">
<tool_name>tool_name</tool_name>
<parameters>
{"param1": "value1", "param2": "value2"}
</parameters>
</tool_call>
</tool_calls>

The available tools are:
{
  "tools": [
    {
      "name": "search_web",
      "description": "Search the internet for information",
      "parameters": {
        "query": "the search query"
      }
    },
    {
      "name": "get_weather",
      "description": "Get the weather for a specific location",
      "parameters": {
        "location": "the location name",
        "unit": "temperature unit (celsius or fahrenheit)"
      }
    }
  ]
}

When using tools, follow these steps:
1. Analyze the user's query and determine which tools are needed
2. Call the appropriate tool using the format above
3. Wait for the tool to return its result
4. Answer the user's question based on the tool result
If the tool result is not enough to answer the user's question, you may make multiple tool calls.
If you can answer the user's question without any tool, answer directly without making a tool call."""

    def build_prompt(self, query: str):
        messages = [
            {"role": "system", "content": self.template},
            {"role": "user", "content": query},
        ]
        return messages
