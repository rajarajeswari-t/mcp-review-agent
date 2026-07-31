from mcp import types

STRICT_NOARG_TOOL = types.Tool(
    name="get_current_time",
    description="Returns the current server time",
    inputSchema={"type": "object", "additionalProperties": False},
)

WITH_PROPERTIES_TOOL = types.Tool(
    name="get_weather",
    description="Get current weather",
    inputSchema={"type": "object", "properties": {"city": {"type": "string"}}},
)
