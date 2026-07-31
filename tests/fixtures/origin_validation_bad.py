from starlette.applications import Starlette
from mcp.server.streamable_http import StreamableHTTPServerTransport

app = Starlette()
transport = StreamableHTTPServerTransport()


@app.route("/mcp", methods=["POST", "GET"])
async def handle_mcp(request):
    # Handles the connection directly with no header validation of any kind.
    return await transport.handle(request)
