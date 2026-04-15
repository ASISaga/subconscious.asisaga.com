"""Azure Functions entry point — Subconscious MCP server.

Architecture
------------
* **MCP endpoint** — ``/mcp/{*rest}``
  FastMCP's streamable-HTTP transport is bridged into Azure Functions via
  ``azure.functions.AsgiMiddleware``.  ``stateless_http=True`` is required
  because Azure Functions does not maintain persistent connections between
  invocations.

  All data access — orchestrations, conversations, schemas, schema contexts —
  is exposed exclusively through the FastMCP protocol (tools, resources,
  prompts, and the ``Conversations`` MCP App).  There are no legacy REST
  ``api/*`` routes.

* **UI** — ``/``
  Lightweight landing page that instructs users to connect via the MCP
  endpoint.

Verbose logging
---------------
Set the ``LOG_LEVEL`` Application Setting to ``DEBUG`` in the Azure portal
(or in ``local.settings.json`` for local development) to enable verbose
request/response traces forwarded to Application Insights.
"""

from __future__ import annotations

import logging

import azure.functions as func

from subconscious.app import get_app_html
from subconscious.logging_config import configure_logging
from subconscious.server import mcp

# Configure logging before anything that might emit log records
configure_logging()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastMCP ASGI adapter — stateless mode required for Azure Functions
# ---------------------------------------------------------------------------
_mcp_asgi = func.AsgiMiddleware(mcp.http_app(stateless_http=True))

# ---------------------------------------------------------------------------
# Azure Functions application
# ---------------------------------------------------------------------------
_app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


# ---------------------------------------------------------------------------
# MCP endpoint — forward all /mcp/* traffic to FastMCP
# ---------------------------------------------------------------------------

@_app.route(route="mcp/{*rest}", methods=["GET", "POST", "DELETE", "PUT"])
async def mcp_endpoint(req: func.HttpRequest) -> func.HttpResponse:
    """Proxy all MCP protocol traffic to the FastMCP streamable-HTTP handler."""
    logger.debug("MCP %s %s", req.method, req.url)
    return await _mcp_asgi.handle_async(req)


# ---------------------------------------------------------------------------
# Homepage — landing page
# ---------------------------------------------------------------------------

@_app.route(route="", methods=["GET"])
def homepage(req: func.HttpRequest) -> func.HttpResponse:
    """Serve the Subconscious landing page."""
    logger.debug("Serving homepage")
    return func.HttpResponse(get_app_html(), mimetype="text/html")


# ---------------------------------------------------------------------------
# Expose the FunctionApp instance as ``app`` for the Azure Functions host
# ---------------------------------------------------------------------------

app = _app
