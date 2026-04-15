"""Azure Functions entry point — Subconscious MCP server.

Architecture
------------
* **Homepage** — ``/``
  Lightweight landing page linking to the MCP endpoint, conversations
  browser, and monitor.  Registered first with minimal dependencies so that
  at least one function is always visible even if optional components fail.

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

* **MCP endpoint** — ``/mcp/{*rest}``
  FastMCP's streamable-HTTP transport is bridged into Azure Functions via
  ``azure.functions.AsgiMiddleware``.  ``stateless_http=True`` is required
  because Azure Functions does not maintain persistent connections between
  invocations.

  All data access — orchestrations, conversations, schemas, schema contexts —
  is exposed through the FastMCP protocol (tools, resources, prompts, and the
  ``Conversations`` MCP App).  There are no legacy ``api/*`` REST routes.

Graceful degradation
--------------------
Each route group is registered inside its own ``try`` block.  If an optional
dependency (e.g. ``fastmcp``, ``azure-data-tables``) is unavailable or raises
during import / initialisation, that group is skipped and an ``ERROR`` log
entry with the full traceback is emitted.  The remaining groups — and most
importantly the homepage — continue to register normally.

Verbose logging
---------------
Set ``LOG_LEVEL`` to ``DEBUG`` in Application Settings / ``local.settings.json``
to enable verbose request/response traces forwarded to Application Insights.
Every successful registration emits a concise ``INFO`` line; every failure
emits a verbose ``ERROR`` with ``exc_info=True``.
"""

from __future__ import annotations

import json
import logging
import os

import azure.functions as func

# ---------------------------------------------------------------------------
# Logging — configured before any code that might emit records.
# Kept inline (no subconscious.logging_config import) so that logging works
# even if the subconscious package itself is broken.
# ---------------------------------------------------------------------------

_LOG_LEVEL_NAME = os.environ.get("LOG_LEVEL", "INFO").strip().upper()
_LOG_LEVEL = getattr(logging, _LOG_LEVEL_NAME, logging.INFO)
logging.basicConfig(
    level=_LOG_LEVEL,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    force=True,
)
for _noisy in ("azure.core", "azure.identity", "urllib3", "httpcore", "httpx"):
    logging.getLogger(_noisy).setLevel(max(_LOG_LEVEL, logging.WARNING))

logger = logging.getLogger(__name__)
logger.info("function_app loading — LOG_LEVEL=%s", _LOG_LEVEL_NAME)

# ---------------------------------------------------------------------------
# Shared response headers
# ---------------------------------------------------------------------------

_JSON_HEADERS = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
_HTML_HEADERS = {"Content-Type": "text/html; charset=utf-8"}

# ---------------------------------------------------------------------------
# Azure Functions application — created before any route registration
# ---------------------------------------------------------------------------

_app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# ---------------------------------------------------------------------------
# Route group 1 — Homepage (minimal deps; always registered first)
# Only requires azure.functions and subconscious.app.  If this fails something
# is fundamentally broken with the Python worker itself.
# ---------------------------------------------------------------------------

try:
    from subconscious.app import get_app_html as _get_app_html

    @_app.route(route="", methods=["GET"])
    def homepage(req: func.HttpRequest) -> func.HttpResponse:
        """Serve the Subconscious landing page."""
        logger.debug("GET / → homepage")
        return func.HttpResponse(_get_app_html(), headers=_HTML_HEADERS)

    logger.info("route registered: GET /")
except Exception as _exc:  # noqa: BLE001
    logger.error("homepage route registration failed: %s", _exc, exc_info=True)

# ---------------------------------------------------------------------------
# Route group 2 — HTML views (depends on subconscious.templates)
# ---------------------------------------------------------------------------

try:
    from subconscious.templates import conversations_page as _conversations_page
    from subconscious.templates import monitor_page as _monitor_page

    @_app.route(route="view/conversations", methods=["GET"])
    def view_conversations(req: func.HttpRequest) -> func.HttpResponse:
        """Serve the HTML5/CSS3 conversation browser SPA."""
        logger.debug("GET /view/conversations")
        return func.HttpResponse(_conversations_page(), headers=_HTML_HEADERS)

    @_app.route(route="monitor", methods=["GET"])
    def view_monitor(req: func.HttpRequest) -> func.HttpResponse:
        """Serve the static monitoring/troubleshooting page."""
        logger.debug("GET /monitor")
        return func.HttpResponse(_monitor_page(), headers=_HTML_HEADERS)

    logger.info("routes registered: GET /view/conversations, GET /monitor")
except Exception as _exc:  # noqa: BLE001
    logger.error("view routes registration failed: %s", _exc, exc_info=True)

# ---------------------------------------------------------------------------
# Route group 3 — Data endpoints (depends on subconscious.storage + server helpers)
# ---------------------------------------------------------------------------

try:
    from subconscious import storage as _storage
    from subconscious.server import _conversation_to_jsonld, _orchestration_to_jsonld
    from subconscious.storage import _demo_conversations_dir, _use_demo_data

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

    logger.info("routes registered: GET /data/orchestrations, GET /data/orchestrations/{oid}, GET /data/health")
except Exception as _exc:  # noqa: BLE001
    logger.error("data routes registration failed: %s", _exc, exc_info=True)

# ---------------------------------------------------------------------------
# Route group 4 — MCP endpoint (depends on fastmcp via subconscious.server)
# The ASGI adapter is built here (not at bare module level) so that a FastMCP
# import/initialisation error does not prevent the other routes from loading.
# ---------------------------------------------------------------------------

try:
    from subconscious.server import mcp as _mcp

    _mcp_asgi = func.AsgiMiddleware(_mcp.http_app(stateless_http=True))

    @_app.route(route="mcp/{*rest}", methods=["GET", "POST", "DELETE", "PUT"])
    async def mcp_endpoint(req: func.HttpRequest) -> func.HttpResponse:
        """Proxy all MCP protocol traffic to the FastMCP streamable-HTTP handler."""
        logger.debug("MCP %s %s", req.method, req.url)
        return await _mcp_asgi.handle_async(req)

    logger.info("route registered: /mcp/{*rest}")
except Exception as _exc:  # noqa: BLE001
    logger.error("MCP route registration failed: %s", _exc, exc_info=True)

# ---------------------------------------------------------------------------
# Startup summary
# ---------------------------------------------------------------------------

logger.info("function_app loaded successfully")

# ---------------------------------------------------------------------------
# Expose the FunctionApp instance as ``app`` for the Azure Functions host
# ---------------------------------------------------------------------------

app = _app
