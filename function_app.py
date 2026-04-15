"""Azure Functions entry point — Subconscious MCP server.

Architecture
------------
* **MCP endpoint** — ``/mcp/{*rest}``
  FastMCP's streamable-HTTP transport is bridged into Azure Functions via
  ``azure.functions.AsgiMiddleware``.  ``stateless_http=True`` is required
  because Azure Functions does not maintain persistent connections between
  invocations.

  All data access — orchestrations, conversations, schemas, schema contexts —
  is exposed through the FastMCP protocol (tools, resources, prompts, and the
  ``Conversations`` MCP App).  There are no legacy ``api/*`` REST routes.

* **Conversation browser** — ``/view/conversations``
  HTML5/CSS3 single-page application.  Fetches Schema.org JSON-LD from the
  ``/data/`` endpoints below and renders conversations entirely client-side
  using vanilla JavaScript.  No React, no server-side templating.

* **Monitor** — ``/monitor``
  Static troubleshooting page showing Azure Functions, FastMCP, and Azure
  Table Storage health.  Polls ``/data/health`` on a 30-second interval.

* **Data endpoints** — ``/data/*``
  Thin JSON-LD bridges consumed by the HTML5/CSS3 templates.  They call the
  same storage layer used by the MCP tools and return Schema.org JSON-LD.

* **Homepage** — ``/``
  Lightweight landing page linking to the MCP endpoint, conversations
  browser, and monitor.

Verbose logging
---------------
Set ``LOG_LEVEL`` to ``DEBUG`` in Application Settings / ``local.settings.json``
to enable verbose request/response traces forwarded to Application Insights.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import azure.functions as func

from subconscious import storage as _storage
from subconscious.app import get_app_html
from subconscious.logging_config import configure_logging
from subconscious.server import (
    _conversation_to_jsonld,
    _orchestration_to_jsonld,
    mcp,
)
from subconscious.templates import conversations_page, monitor_page

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

_JSON_HEADERS = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
_HTML_HEADERS = {"Content-Type": "text/html; charset=utf-8"}


# ---------------------------------------------------------------------------
# MCP endpoint — forward all /mcp/* traffic to FastMCP
# ---------------------------------------------------------------------------

@_app.route(route="mcp/{*rest}", methods=["GET", "POST", "DELETE", "PUT"])
async def mcp_endpoint(req: func.HttpRequest) -> func.HttpResponse:
    """Proxy all MCP protocol traffic to the FastMCP streamable-HTTP handler."""
    logger.debug("MCP %s %s", req.method, req.url)
    return await _mcp_asgi.handle_async(req)


# ---------------------------------------------------------------------------
# HTML5/CSS3 views — client-side Schema.org JSON-LD rendering
# ---------------------------------------------------------------------------

@_app.route(route="view/conversations", methods=["GET"])
def view_conversations(req: func.HttpRequest) -> func.HttpResponse:
    """Serve the HTML5/CSS3 conversation browser SPA."""
    logger.debug("Serving conversations page")
    return func.HttpResponse(conversations_page(), headers=_HTML_HEADERS)


@_app.route(route="monitor", methods=["GET"])
def view_monitor(req: func.HttpRequest) -> func.HttpResponse:
    """Serve the static monitoring/troubleshooting page."""
    logger.debug("Serving monitor page")
    return func.HttpResponse(monitor_page(), headers=_HTML_HEADERS)


# ---------------------------------------------------------------------------
# Data endpoints — Schema.org JSON-LD feeds for the HTML5/CSS3 templates
# ---------------------------------------------------------------------------

@_app.route(route="data/orchestrations", methods=["GET"])
def data_orchestrations(req: func.HttpRequest) -> func.HttpResponse:
    """Return all orchestrations as a JSON array of Schema.org Action JSON-LD.

    Query parameter ``status`` filters by ``active``, ``completed``, or ``failed``.
    """
    status = req.params.get("status") or None
    raw = _storage.list_orchestrations(status)
    body = json.dumps([_orchestration_to_jsonld(o) for o in raw])
    return func.HttpResponse(body, headers=_JSON_HEADERS)


@_app.route(route="data/orchestrations/{oid}", methods=["GET"])
def data_orchestration(req: func.HttpRequest) -> func.HttpResponse:
    """Return a single orchestration as Schema.org Action JSON-LD.

    The ``object`` property contains the full Schema.org Conversation JSON-LD
    with all messages embedded, ready for client-side rendering.
    """
    oid = req.route_params.get("oid", "")
    orch = _storage.get_orchestration(oid)
    if orch is None:
        body = json.dumps({"error": f"Orchestration '{oid}' not found"})
        return func.HttpResponse(body, status_code=404, headers=_JSON_HEADERS)
    messages = _storage.get_conversation(oid)
    doc = _orchestration_to_jsonld(orch)
    doc["object"] = _conversation_to_jsonld(oid, messages, orch)
    return func.HttpResponse(json.dumps(doc), headers=_JSON_HEADERS)


@_app.route(route="data/health", methods=["GET"])
def data_health(req: func.HttpRequest) -> func.HttpResponse:
    """Return health/status information for the monitor page.

    Response fields:
      - ``storage``: ``"demo"`` when no Azure Storage connection is set, else ``"ok"``.
      - ``demo_conversations``: count of demo JSON files (only when in demo mode).
      - ``demo_data_dir``: path to the demo data directory (demo mode only).
      - ``version``: human-readable server version string.
    """
    from subconscious.storage import _demo_conversations_dir, _use_demo_data

    demo = _use_demo_data()
    demo_count: int | None = None
    demo_dir: str | None = None
    if demo:
        data_dir = _demo_conversations_dir()
        if data_dir.exists():
            demo_count = len(list(data_dir.glob("*.json")))
            demo_dir = str(data_dir)

    body = json.dumps({
        "@context": "https://schema.org/",
        "@type": "DigitalDocument",
        "name": "Subconscious Health Status",
        "version": "Subconscious 2.0 · FastMCP on Azure Functions v4",
        "storage": "demo" if demo else "ok",
        "demo_conversations": demo_count,
        "demo_data_dir": demo_dir,
        "status": "ok",
    })
    return func.HttpResponse(body, headers=_JSON_HEADERS)


# ---------------------------------------------------------------------------
# Homepage — landing page
# ---------------------------------------------------------------------------

@_app.route(route="", methods=["GET"])
def homepage(req: func.HttpRequest) -> func.HttpResponse:
    """Serve the Subconscious landing page."""
    logger.debug("Serving homepage")
    return func.HttpResponse(get_app_html(), headers=_HTML_HEADERS)


# ---------------------------------------------------------------------------
# Expose the FunctionApp instance as ``app`` for the Azure Functions host
# ---------------------------------------------------------------------------

app = _app
