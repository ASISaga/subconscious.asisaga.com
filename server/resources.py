"""MCP resources — orchestration, schema, and schema-context resources."""

from __future__ import annotations

import json

from server import _conversation_to_jsonld, _orchestration_to_jsonld, mcp
from server.tools import _resolve_dimension
from storage import conversations as storage_conv
from storage import schemas as schema_storage


@mcp.resource("orchestration://{orchestration_id}")
def orchestration_resource(orchestration_id: str) -> str:
    """Return orchestration metadata and its full conversation history as Schema.org JSON-LD."""
    orch = storage_conv.get_orchestration(orchestration_id)
    if orch is None:
        return json.dumps({"error": f"Orchestration '{orchestration_id}' not found"})
    messages = storage_conv.get_conversation(orchestration_id)
    doc = _orchestration_to_jsonld(orch)
    doc["object"] = _conversation_to_jsonld(orchestration_id, messages, orch)
    return json.dumps(doc)


@mcp.resource("schema://{schema_name}")
def schema_resource(schema_name: str) -> str:
    """Return a boardroom mind schema definition by name as JSON.

    Available schema names: manas, buddhi, ahankara, chitta, action-plan,
    entity-context, entity-content.
    """
    data = schema_storage.get_schema(schema_name)
    if data is None:
        available = list(schema_storage.SCHEMA_REGISTRY.keys())
        return json.dumps({"error": f"Schema '{schema_name}' not found", "available": available})
    return json.dumps(data)


@mcp.resource("schema-context://{schema_name}/{context_id}")
def schema_context_resource(schema_name: str, context_id: str) -> str:
    """Return a stored schema context document as JSON-LD.

    Args:
        schema_name: The mind schema name (e.g. ``manas``, ``buddhi``).
        context_id: The context identifier (e.g. agent id ``ceo``).
    """
    result = schema_storage.get_schema_context(schema_name, context_id)
    if result is None:
        return json.dumps({"error": f"Schema context '{schema_name}/{context_id}' not found"})
    return json.dumps(result)


@mcp.resource("mind://{agent_id}/{dimension}")
def agent_mind_resource(agent_id: str, dimension: str) -> str:
    """Return an atomic mind-state document for a CXO agent by unique ID and dimension.

    This resource provides direct URI-addressable access to any mind-state file
    owned by an agent.  The ``dimension`` path mirrors the directory layout in
    the ``mind/`` repository directory:

    * ``mind://ceo/manas`` — CEO's working memory state
    * ``mind://cfo/buddhi`` — CFO's intellect document
    * ``mind://cto/chitta`` — CTO's pure intelligence document
    * ``mind://coo/responsibilities/manager`` — COO's manager responsibilities
    * ``mind://cmo/manas/content/company`` — CMO's mutable company perspective

    See :func:`server.tools.get_agent_state` for the full list of dimension
    formats.

    Args:
        agent_id: Unique CXO agent identifier (e.g. ``"ceo"``).
        dimension: Dimension path (e.g. ``"manas"``, ``"responsibilities/entrepreneur"``).
    """
    try:
        schema_name, context_id = _resolve_dimension(agent_id, dimension)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})
    result = schema_storage.get_schema_context(schema_name, context_id)
    if result is None:
        return json.dumps({
            "error": f"No state found for agent '{agent_id}' dimension '{dimension}'"
        })
    return json.dumps(result)
