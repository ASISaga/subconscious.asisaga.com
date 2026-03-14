import azure.functions as func

from subconscious.server import mcp

# Expose the FastMCP server as an Azure Functions ASGI app.
# SSE endpoint:     <function-url>/sse       (Server-Sent Events transport)
# Messages endpoint: <function-url>/messages  (SSE message posting)
app = func.AsgiFunctionApp(
    app=mcp.http_app(transport="sse"),
    http_auth_level=func.AuthLevel.ANONYMOUS,
)