from mcp import types

WEATHER_TOOL = types.Tool(
    name="Get Weather!!",
    description="Get current weather",
    inputSchema={"type": "object", "properties": {"city": {"type": "string"}}},
)

# Duplicate of a name declared elsewhere in this file
SEARCH_TOOL_1 = types.Tool(name="search", description="first search tool", inputSchema={"type": "object"})
SEARCH_TOOL_2 = types.Tool(name="search", description="second search tool, same name", inputSchema={"type": "object"})
