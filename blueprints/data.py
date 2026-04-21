"""Data blueprint — thin JSON-LD bridges consumed by the HTML5/CSS3 templates.

Routes
------
* ``GET /data/orchestrations`` — list all orchestrations as Schema.org Action JSON-LD.
* ``GET /data/orchestrations/{oid}`` — single orchestration with full conversation.
* ``GET /data/health`` — health/status information for the monitor page.
"""

from __future__ import annotations

import json
import logging

import azure.functions as func

from server import _conversation_to_jsonld, _orchestration_to_jsonld
from storage import conversations as storage_conv
from storage.conversations import _demo_conversations_dir, _use_demo_data

logger = logging.getLogger(__name__)

bp = func.Blueprint()

_JSON_HEADERS = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}


@bp.route(route="data/orchestrations", methods=["GET"])
def data_orchestrations(req: func.HttpRequest) -> func.HttpResponse:
    """Return all orchestrations as a JSON array of Schema.org Action JSON-LD.

    Query parameter ``status`` filters by ``active``, ``completed``, or ``failed``.
    """
    status = req.params.get("status") or None
    raw = storage_conv.list_orchestrations(status)
    body = json.dumps([_orchestration_to_jsonld(o) for o in raw])
    return func.HttpResponse(body, headers=_JSON_HEADERS)


@bp.route(route="data/orchestrations/{oid}", methods=["GET"])
def data_orchestration(req: func.HttpRequest) -> func.HttpResponse:
    """Return a single orchestration as Schema.org Action JSON-LD.

    The ``object`` property contains the full Schema.org Conversation JSON-LD
    with all messages embedded, ready for client-side rendering.
    """
    oid = req.route_params.get("oid", "")
    orch = storage_conv.get_orchestration(oid)
    if orch is None:
        body = json.dumps({"error": f"Orchestration '{oid}' not found"})
        return func.HttpResponse(body, status_code=404, headers=_JSON_HEADERS)
    messages = storage_conv.get_conversation(oid)
    doc = _orchestration_to_jsonld(orch)
    doc["object"] = _conversation_to_jsonld(oid, messages, orch)
    return func.HttpResponse(json.dumps(doc), headers=_JSON_HEADERS)


@bp.route(route="data/health", methods=["GET"])
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
