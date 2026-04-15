"""Azure Functions entry point — Subconscious MCP server.

Architecture
------------
* **MCP endpoint** — ``/mcp/{*rest}``
  FastMCP's streamable-HTTP transport is bridged into Azure Functions via
  ``azure.functions.AsgiMiddleware``.  ``stateless_http=True`` is required
  because Azure Functions does not maintain persistent connections between
  invocations.

* **REST API** — ``/api/*``
  Thin Azure Functions routes that call pure-Python handler functions from
  ``subconscious.app`` and serialise the results to JSON.  No Starlette
  dependency in this layer.

* **UI** — ``/``
  Single-page HTML application served from an embedded string.

Verbose logging
---------------
Set the ``LOG_LEVEL`` Application Setting to ``DEBUG`` in the Azure portal
(or in ``local.settings.json`` for local development) to enable verbose
request/response traces forwarded to Application Insights.
"""

from __future__ import annotations

import json
import logging

import azure.functions as func

from subconscious import app as handlers
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
# Health check
# ---------------------------------------------------------------------------

@_app.route(route="api/health", methods=["GET"])
def api_health(req: func.HttpRequest) -> func.HttpResponse:
    """Return service health status (Schema.org HealthAspect JSON-LD)."""
    logger.debug("Health check from %s", req.headers.get("x-forwarded-for", "unknown"))
    body = handlers.get_health()
    return func.HttpResponse(json.dumps(body), mimetype="application/ld+json")


# ---------------------------------------------------------------------------
# Orchestrations
# ---------------------------------------------------------------------------

@_app.route(route="api/orchestrations", methods=["GET"])
def api_list_orchestrations(req: func.HttpRequest) -> func.HttpResponse:
    """List all orchestrations, optionally filtered by ``status`` query param."""
    status = req.params.get("status")
    logger.debug("List orchestrations status=%s", status)
    data = handlers.list_orchestrations(status)
    return func.HttpResponse(json.dumps(data), mimetype="application/json")


@_app.route(route="api/orchestrations/{oid}", methods=["GET"])
def api_get_orchestration(req: func.HttpRequest, oid: str) -> func.HttpResponse:
    """Return a single orchestration (Schema.org Action JSON-LD)."""
    logger.debug("Get orchestration %s", oid)
    data = handlers.get_orchestration(oid)
    if data is None:
        return func.HttpResponse(
            json.dumps({"error": "Not found"}),
            status_code=404,
            mimetype="application/json",
        )
    return func.HttpResponse(json.dumps(data), mimetype="application/ld+json")


@_app.route(route="api/orchestrations/{oid}/messages", methods=["GET"])
def api_get_conversation(req: func.HttpRequest, oid: str) -> func.HttpResponse:
    """Return conversation messages (Schema.org Conversation JSON-LD)."""
    limit_raw = req.params.get("limit", "200")
    try:
        limit = int(limit_raw)
    except ValueError:
        limit = 200
    logger.debug("Get conversation %s limit=%d", oid, limit)
    data = handlers.get_conversation(oid, limit=limit)
    return func.HttpResponse(json.dumps(data), mimetype="application/ld+json")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

@_app.route(route="api/schemas", methods=["GET"])
def api_list_schemas(req: func.HttpRequest) -> func.HttpResponse:
    """List all registered boardroom mind schemas."""
    logger.debug("List schemas")
    data = handlers.list_schemas()
    return func.HttpResponse(json.dumps(data), mimetype="application/json")


@_app.route(route="api/schemas/{name}", methods=["GET"])
def api_get_schema(req: func.HttpRequest, name: str) -> func.HttpResponse:
    """Return a schema definition by name."""
    logger.debug("Get schema %s", name)
    data = handlers.get_schema(name)
    if data is None:
        available = handlers.get_schema_available()
        return func.HttpResponse(
            json.dumps({"error": "Schema not found", "available": available}),
            status_code=404,
            mimetype="application/json",
        )
    return func.HttpResponse(json.dumps(data), mimetype="application/json")


# ---------------------------------------------------------------------------
# Schema contexts
# ---------------------------------------------------------------------------

@_app.route(route="api/schema-contexts", methods=["GET"])
def api_list_schema_contexts(req: func.HttpRequest) -> func.HttpResponse:
    """List stored schema contexts, optionally filtered by ``schema`` param."""
    schema_name = req.params.get("schema")
    logger.debug("List schema-contexts schema=%s", schema_name)
    data = handlers.list_schema_contexts(schema_name)
    return func.HttpResponse(json.dumps(data), mimetype="application/json")


@_app.route(route="api/schema-contexts/{schema_name}/{context_id}", methods=["GET", "PUT"])
def api_schema_context(
    req: func.HttpRequest,
    schema_name: str,
    context_id: str,
) -> func.HttpResponse:
    """GET or PUT a schema context document."""
    if req.method == "GET":
        logger.debug("Get schema-context %s/%s", schema_name, context_id)
        result = handlers.get_schema_context(schema_name, context_id)
        if result is None:
            return func.HttpResponse(
                json.dumps({"error": "Schema context not found"}),
                status_code=404,
                mimetype="application/json",
            )
        return func.HttpResponse(json.dumps(result), mimetype="application/ld+json")

    # PUT
    logger.debug("Store schema-context %s/%s", schema_name, context_id)
    try:
        body = req.get_json()
    except (ValueError, TypeError):
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON body"}),
            status_code=400,
            mimetype="application/json",
        )
    result = handlers.store_schema_context(schema_name, context_id, body)
    return func.HttpResponse(json.dumps(result), mimetype="application/json")


# ---------------------------------------------------------------------------
# Homepage — single-page MCP Apps UI
# ---------------------------------------------------------------------------

@_app.route(route="", methods=["GET"])
def homepage(req: func.HttpRequest) -> func.HttpResponse:
    """Serve the built-in MCP Apps single-page UI."""
    logger.debug("Serving homepage")
    return func.HttpResponse(handlers._APP_HTML, mimetype="text/html")


# ---------------------------------------------------------------------------
# Expose the FunctionApp instance as ``app`` for the Azure Functions host
# ---------------------------------------------------------------------------

app = _app
