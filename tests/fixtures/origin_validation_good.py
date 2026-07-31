from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from mcp.server.streamable_http import StreamableHTTPServerTransport

app = Starlette()
transport = StreamableHTTPServerTransport()

ALLOWED_ORIGINS = {"https://trusted-client.example.com"}


@app.route("/mcp", methods=["POST", "GET"])
async def handle_mcp(request):
    origin = request.headers.get("origin")
    if origin is not None and origin not in ALLOWED_ORIGINS:
        return PlainTextResponse("Forbidden", status_code=403)
    return await transport.handle(request)
