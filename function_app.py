import azure.functions as func

from subconscious.server import mcp

# Expose the FastMCP server as an Azure Functions ASGI app.
# The MCP endpoint is available at <function-url>/mcp (Streamable HTTP transport).
app = func.AsgiFunctionApp(
    app=mcp.http_app(),
    http_auth_level=func.AuthLevel.ANONYMOUS,
)