"""Azure Functions entry point — Subconscious MCP server.

Architecture
------------
Routes are organised into semantic :class:`azure.functions.Blueprint` modules
and registered here.  Each blueprint owns one concern:

* :mod:`blueprints.homepage` — ``GET /`` landing page.
* :mod:`blueprints.views` — ``GET /view/conversations`` and ``GET /monitor``.
* :mod:`blueprints.data` — ``GET /data/*`` JSON-LD data endpoints.
* :mod:`blueprints.mcp_endpoint` — ``/mcp/{*rest}`` FastMCP proxy.

Verbose logging
---------------
Set ``LOG_LEVEL`` to ``DEBUG`` in Application Settings / ``local.settings.json``
to enable verbose request/response traces forwarded to Application Insights.
"""

from __future__ import annotations

import logging
import os

import azure.functions as func

# ---------------------------------------------------------------------------
# Logging — configured before any blueprint is imported.
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
# Azure Functions application
# ---------------------------------------------------------------------------

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# ---------------------------------------------------------------------------
# Register blueprints — each import may raise if an optional dep is missing;
# remaining blueprints continue to register normally.
# ---------------------------------------------------------------------------

try:
    from blueprints.homepage import bp as _homepage_bp
    app.register_functions(_homepage_bp)
    logger.info("blueprint registered: homepage (GET /)")
except Exception as _exc:  # noqa: BLE001
    logger.error("homepage blueprint registration failed: %s", _exc, exc_info=True)

try:
    from blueprints.views import bp as _views_bp
    app.register_functions(_views_bp)
    logger.info("blueprint registered: views (GET /view/conversations, GET /monitor)")
except Exception as _exc:  # noqa: BLE001
    logger.error("views blueprint registration failed: %s", _exc, exc_info=True)

try:
    from blueprints.data import bp as _data_bp
    app.register_functions(_data_bp)
    logger.info("blueprint registered: data (GET /data/*)")
except Exception as _exc:  # noqa: BLE001
    logger.error("data blueprint registration failed: %s", _exc, exc_info=True)

try:
    from blueprints.mcp_endpoint import bp as _mcp_bp
    app.register_functions(_mcp_bp)
    logger.info("blueprint registered: mcp_endpoint (/mcp/{*rest})")
except Exception as _exc:  # noqa: BLE001
    logger.error("mcp_endpoint blueprint registration failed: %s", _exc, exc_info=True)

# ---------------------------------------------------------------------------
# Startup summary
# ---------------------------------------------------------------------------

logger.info("function_app loaded successfully")
