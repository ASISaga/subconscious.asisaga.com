"""Homepage blueprint — serves the Subconscious landing page at ``GET /``.

This is the first blueprint registered so that at least one function is always
visible even if optional components fail to load.
"""

from __future__ import annotations

import logging

import azure.functions as func

from templates import get_app_html

logger = logging.getLogger(__name__)

bp = func.Blueprint()

_HTML_HEADERS = {"Content-Type": "text/html; charset=utf-8"}


@bp.route(route="", methods=["GET"])
def homepage(req: func.HttpRequest) -> func.HttpResponse:
    """Serve the Subconscious landing page."""
    logger.debug("GET / → homepage")
    return func.HttpResponse(get_app_html(), headers=_HTML_HEADERS)
