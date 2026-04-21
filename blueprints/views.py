"""Views blueprint — serves the HTML5/CSS3 browser pages.

Routes
------
* ``GET /view/conversations`` — Conversation browser SPA.
* ``GET /monitor`` — Static monitoring/troubleshooting page.
"""

from __future__ import annotations

import logging

import azure.functions as func

from templates import conversations_page, monitor_page

logger = logging.getLogger(__name__)

bp = func.Blueprint()

_HTML_HEADERS = {"Content-Type": "text/html; charset=utf-8"}


@bp.route(route="view/conversations", methods=["GET"])
def view_conversations(req: func.HttpRequest) -> func.HttpResponse:
    """Serve the HTML5/CSS3 conversation browser SPA."""
    logger.debug("GET /view/conversations")
    return func.HttpResponse(conversations_page(), headers=_HTML_HEADERS)


@bp.route(route="monitor", methods=["GET"])
def view_monitor(req: func.HttpRequest) -> func.HttpResponse:
    """Serve the static monitoring/troubleshooting page."""
    logger.debug("GET /monitor")
    return func.HttpResponse(monitor_page(), headers=_HTML_HEADERS)
