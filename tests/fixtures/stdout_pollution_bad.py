from mcp.server.stdio import stdio_server


async def run():
    async with stdio_server() as (read_stream, write_stream):
        print("server starting up")  # pollutes stdout, breaks the JSON-RPC stream
        await serve(read_stream, write_stream)
