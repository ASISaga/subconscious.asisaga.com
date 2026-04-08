import azure.functions as func

from subconscious.app import create_app

# Expose the combined ASGI application (MCP endpoint + REST API + UI) as an
# Azure Functions app.  The MCP streamable-HTTP endpoint lives at /mcp,
# the REST API at /api/*, and the MCP Apps UI at /.
app = func.AsgiFunctionApp(
    app=create_app(),
    http_auth_level=func.AuthLevel.ANONYMOUS,
)
