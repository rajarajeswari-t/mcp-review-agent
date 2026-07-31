import sys

from mcp.server.stdio import stdio_server


async def run():
    async with stdio_server() as (read_stream, write_stream):
        print("server starting up", file=sys.stderr)
        await serve(read_stream, write_stream)
