"""MCP endpoint blueprint — proxies all MCP protocol traffic to FastMCP.

Route
-----
* ``GET|POST|DELETE|PUT /mcp/{*rest}`` — FastMCP streamable-HTTP transport via
  ``azure.functions.AsgiMiddleware``.

``stateless_http=True`` is required because Azure Functions does not maintain
persistent connections between invocations.
"""

from __future__ import annotations

import logging

import azure.functions as func

from server import mcp

logger = logging.getLogger(__name__)

bp = func.Blueprint()

_mcp_asgi = func.AsgiMiddleware(mcp.http_app(stateless_http=True))


@bp.route(route="mcp/{*rest}", methods=["GET", "POST", "DELETE", "PUT"])
async def mcp_endpoint(req: func.HttpRequest) -> func.HttpResponse:
    """Proxy all MCP protocol traffic to the FastMCP streamable-HTTP handler."""
    logger.debug("MCP %s %s", req.method, req.url)
    return await _mcp_asgi.handle_async(req)
