from mcp import types

WEATHER_TOOL = types.Tool(
    name="get_weather",
    description="Get current weather",
    inputSchema={"type": "object", "properties": {"city": {"type": "string"}}},
)

SEARCH_TOOL = types.Tool(
    name="search_files",
    description="Search project files",
    inputSchema={"type": "object", "properties": {"query": {"type": "string"}}},
)

# Unrelated `name=` kwarg on a non-MCP class — must NOT be flagged.
class Person:
    def __init__(self, name):
        self.name = name
