from mcp import types

# inputSchema is None — a hard spec violation (MUST be a valid JSON Schema object)
BROKEN_TOOL = types.Tool(
    name="get_current_time",
    description="Returns the current server time",
    inputSchema=None,
)

# Looks like a no-arg tool but doesn't set additionalProperties: false
LOOSE_TOOL = types.Tool(
    name="ping",
    description="Health check",
    inputSchema={"type": "object"},
)
