"""FastMCP server — multi-agent conversation persistence and schema context management.

Exposes orchestration management, message persistence, conversation retrieval,
boardroom mind schema definitions, and schema context persistence/retrieval as
MCP Tools and Resources.  Designed for use by Microsoft Agent Framework
orchestrations deployed on Foundry Agent Service.

MCP Apps
--------
A ``FastMCPApp`` named ``Conversations`` provides a rich Prefab UI that an MCP
client (e.g. Claude Desktop, Copilot) can render to browse orchestrations and
their full Schema.org JSON-LD conversation histories without leaving the chat
interface.  The UI entry-point tool is ``show_conversations`` and backend data
tools are ``load_orchestrations`` and ``load_conversation``.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastmcp import FastMCP, FastMCPApp

from subconscious import schema_storage, storage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema.org JSON-LD annotation helpers (shared between tools and the App)
# ---------------------------------------------------------------------------

_SCHEMA_ORG = "https://schema.org/"

_ACTION_STATUS: dict[str, str] = {
    "active": "https://schema.org/ActiveActionStatus",
    "completed": "https://schema.org/CompletedActionStatus",
    "failed": "https://schema.org/FailedActionStatus",
}


def _orchestration_to_jsonld(orch: dict[str, Any]) -> dict[str, Any]:
    """Return *orch* annotated with Schema.org Action JSON-LD fields."""
    status_uri = _ACTION_STATUS.get(orch.get("status", ""), _ACTION_STATUS["active"])
    return {
        "@context": _SCHEMA_ORG,
        "@type": "Action",
        "@id": f"subconscious://orchestrations/{orch['orchestration_id']}",
        "actionStatus": status_uri,
        **orch,
    }


def _message_to_jsonld(msg: dict[str, Any]) -> dict[str, Any]:
    """Return *msg* annotated with Schema.org Message JSON-LD fields."""
    return {
        "@context": _SCHEMA_ORG,
        "@type": "Message",
        "@id": f"subconscious://messages/{msg['orchestration_id']}/{msg['sequence']}",
        "sender": {"@type": "Person", "identifier": msg.get("agent_id", "")},
        "dateCreated": msg.get("created_at", ""),
        "text": msg.get("content", ""),
        **msg,
    }


def _conversation_to_jsonld(
    orchestration_id: str,
    messages: list[dict[str, Any]],
    orch: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a Schema.org Conversation JSON-LD document."""
    return {
        "@context": _SCHEMA_ORG,
        "@type": "Conversation",
        "@id": f"subconscious://conversations/{orchestration_id}",
        "orchestration_id": orchestration_id,
        "purpose": orch.get("purpose", "") if orch else "",
        "status": orch.get("status", "unknown") if orch else "unknown",
        "actionStatus": _ACTION_STATUS.get(
            orch.get("status", "") if orch else "",
            _ACTION_STATUS["active"],
        ),
        "messages": [_message_to_jsonld(m) for m in messages],
        "total": len(messages),
    }


# ---------------------------------------------------------------------------
# FastMCP server instance
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "Subconscious",
    instructions=(
        "Multi-agent conversation persistence and schema context server.  "
        "Persist and retrieve orchestration conversations from Azure Table Storage.  "
        "Use 'create_orchestration' to register a new orchestration, "
        "'persist_message' or 'persist_conversation_turn' to append messages, "
        "and 'get_conversation' to retrieve the full history by orchestration ID.  "
        "Use 'list_schemas' and 'get_schema' to explore boardroom mind schema definitions.  "
        "Use 'store_schema_context' and 'get_schema_context' to persist and retrieve "
        "JSON-LD documents (agent Manas, Buddhi, Ahankara, Chitta, and entity perspectives) "
        "that conform to the boardroom mind schemas.  "
        "Use 'show_conversations' to open the interactive conversation browser UI."
    ),
)


# ---------------------------------------------------------------------------
# FastMCPApp — Conversations App (data tools, app-internal)
# ---------------------------------------------------------------------------

conversations_app = FastMCPApp("Conversations")


@conversations_app.tool()
def fetch_orchestrations(status: str | None = None) -> list[dict[str, Any]]:
    """Load all orchestrations as Schema.org Action JSON-LD documents.

    Called by the Conversations UI to populate the orchestration list.

    Args:
        status: Optional filter — ``active``, ``completed``, or ``failed``.

    Returns:
        List of Schema.org Action JSON-LD documents.
    """
    raw = storage.list_orchestrations(status)
    return [_orchestration_to_jsonld(o) for o in raw]


@conversations_app.tool()
def fetch_conversation(orchestration_id: str) -> dict[str, Any]:
    """Load a full conversation as a Schema.org Conversation JSON-LD document.

    Called by the Conversations UI when the user selects an orchestration.

    Args:
        orchestration_id: The orchestration whose conversation to load.

    Returns:
        Schema.org Conversation JSON-LD document with embedded messages.
    """
    msgs = storage.get_conversation(orchestration_id)
    orch = storage.get_orchestration(orchestration_id)
    return _conversation_to_jsonld(orchestration_id, msgs, orch)


# Register the Conversations MCP App with the server
mcp.add_provider(conversations_app)


# ---------------------------------------------------------------------------
# MCP Tool — show_conversations (model-visible entry point)
# ---------------------------------------------------------------------------

@mcp.tool()
def show_conversations(status: str | None = None) -> dict[str, Any]:
    """Browse multi-agent orchestration conversations.

    Returns a Schema.org ItemList of orchestrations as JSON-LD and a
    ``view_url`` pointing to the interactive HTML5/CSS3 conversation browser,
    which renders the data entirely client-side (vanilla JavaScript, no React).

    Args:
        status: Optional filter — ``active``, ``completed``, or ``failed``.

    Returns:
        Schema.org ItemList JSON-LD with ``view_url`` for the browser UI.
    """
    orchestrations = fetch_orchestrations(status)
    qs = f"?status={status}" if status else ""
    view_url = f"/view/conversations{qs}"
    return {
        "@context": _SCHEMA_ORG,
        "@type": "ItemList",
        "name": "Multi-Agent Conversations",
        "description": (
            f"Open the conversation browser at: {view_url}  "
            "Rendered client-side from Schema.org JSON-LD."
        ),
        "view_url": view_url,
        "numberOfItems": len(orchestrations),
        "itemListElement": orchestrations,
    }


# ---------------------------------------------------------------------------
# MCP Resources — orchestrations
# ---------------------------------------------------------------------------

@mcp.resource("orchestration://{orchestration_id}")
def orchestration_resource(orchestration_id: str) -> str:
    """Return orchestration metadata and its full conversation history as Schema.org JSON-LD."""
    orch = storage.get_orchestration(orchestration_id)
    if orch is None:
        return json.dumps({"error": f"Orchestration '{orchestration_id}' not found"})
    messages = storage.get_conversation(orchestration_id)
    doc = _orchestration_to_jsonld(orch)
    doc["object"] = _conversation_to_jsonld(orchestration_id, messages, orch)
    return json.dumps(doc)


# ---------------------------------------------------------------------------
# MCP Resources — schemas
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# MCP Tools — orchestration lifecycle
# ---------------------------------------------------------------------------

@mcp.tool()
def create_orchestration(
    orchestration_id: str,
    purpose: str,
    agents: list[str] | None = None,
) -> dict[str, Any]:
    """Register a new orchestration so that conversation messages can be stored.

    Args:
        orchestration_id: Unique identifier for the orchestration (typically from Foundry Agent Service).
        purpose: Human-readable description of the orchestration's goal.
        agents: Optional list of agent identifiers participating in this orchestration.

    Returns:
        The newly created orchestration record.
    """
    return storage.create_orchestration(orchestration_id, purpose, agents)


@mcp.tool()
def complete_orchestration(
    orchestration_id: str,
    summary: str | None = None,
) -> dict[str, Any]:
    """Mark an orchestration as completed and optionally attach a summary.

    Args:
        orchestration_id: The orchestration to complete.
        summary: Optional concluding summary of the orchestration outcome.

    Returns:
        The updated orchestration record.
    """
    return storage.update_orchestration_status(orchestration_id, "completed", summary)


@mcp.tool()
def list_orchestrations(status: str | None = None) -> list[dict[str, Any]]:
    """List all known orchestrations as Schema.org Action JSON-LD documents.

    Args:
        status: Filter by ``active``, ``completed``, or ``failed``.

    Returns:
        A list of Schema.org Action JSON-LD orchestration records.
    """
    raw = storage.list_orchestrations(status)
    return [_orchestration_to_jsonld(o) for o in raw]


# ---------------------------------------------------------------------------
# MCP Tools — message persistence
# ---------------------------------------------------------------------------

@mcp.tool()
def persist_message(
    orchestration_id: str,
    agent_id: str,
    role: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append a single message to an orchestration conversation.

    Args:
        orchestration_id: The owning orchestration.
        agent_id: Identifier of the agent that produced the message.
        role: Message role — ``user``, ``assistant``, ``system``, or ``tool``.
        content: Full text content of the message.
        metadata: Optional structured metadata (serialised as JSON).

    Returns:
        Confirmation with the assigned sequence key and timestamp.
    """
    return storage.persist_message(orchestration_id, agent_id, role, content, metadata)


@mcp.tool()
def persist_conversation_turn(
    orchestration_id: str,
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    """Persist multiple messages for one orchestration turn in a single call.

    Each element in *messages* must contain ``agent_id``, ``role``, and
    ``content`` keys, with an optional ``metadata`` dict.

    Args:
        orchestration_id: The owning orchestration.
        messages: List of message dicts to persist.

    Returns:
        Summary with the number of messages stored and their metadata.
    """
    results = storage.persist_messages(orchestration_id, messages)
    return {"orchestration_id": orchestration_id, "persisted": len(results), "messages": results}


# ---------------------------------------------------------------------------
# MCP Tools — conversation retrieval
# ---------------------------------------------------------------------------

@mcp.tool()
def get_conversation(
    orchestration_id: str,
    limit: int = 200,
) -> dict[str, Any]:
    """Retrieve the full conversation for an orchestration as Schema.org JSON-LD.

    Args:
        orchestration_id: The orchestration whose conversation to retrieve.
        limit: Maximum number of messages to return (default 200).

    Returns:
        Schema.org Conversation JSON-LD document with embedded messages.
    """
    messages = storage.get_conversation(orchestration_id, limit=limit)
    orch = storage.get_orchestration(orchestration_id)
    return _conversation_to_jsonld(orchestration_id, messages, orch)


# ---------------------------------------------------------------------------
# MCP Tools — schema definitions (read-only)
# ---------------------------------------------------------------------------

@mcp.tool()
def list_schemas() -> list[dict[str, Any]]:
    """List all available boardroom mind schema definitions.

    Returns:
        List of schema metadata records including ``name``, ``filename``,
        ``available``, ``title``, and ``description``.
    """
    return schema_storage.list_schemas()


@mcp.tool()
def get_schema(schema_name: str) -> dict[str, Any]:
    """Retrieve a boardroom mind schema definition by name.

    Args:
        schema_name: One of ``manas``, ``buddhi``, ``ahankara``, ``chitta``,
            ``action-plan``, ``entity-context``, ``entity-content``.

    Returns:
        The full JSON Schema object, or an error dict if not found.
    """
    data = schema_storage.get_schema(schema_name)
    if data is None:
        available = list(schema_storage.SCHEMA_REGISTRY.keys())
        return {"error": f"Schema '{schema_name}' not found", "available": available}
    return data


# ---------------------------------------------------------------------------
# MCP Tools — schema context persistence
# ---------------------------------------------------------------------------

@mcp.tool()
def store_schema_context(
    schema_name: str,
    context_id: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Persist a JSON-LD document conforming to a boardroom mind schema.

    Agents use this tool to write their mind-layer documents (Manas, Buddhi,
    Ahankara, Chitta, or entity perspectives) to durable storage so that they
    can be retrieved in future sessions.

    Args:
        schema_name: The schema this document conforms to — one of
            ``manas``, ``buddhi``, ``ahankara``, ``chitta``,
            ``action-plan``, ``entity-context``, ``entity-content``.
        context_id: Unique key for this context — typically the agent id
            (e.g. ``"ceo"``) or a compound key for entity perspectives
            (e.g. ``"ceo/company"``).
        data: The JSON-LD document to persist.

    Returns:
        Confirmation with ``schema_name``, ``context_id``, and ``updated_at``.
    """
    return schema_storage.store_schema_context(schema_name, context_id, data)


@mcp.tool()
def get_schema_context(
    schema_name: str,
    context_id: str,
) -> dict[str, Any]:
    """Retrieve a stored boardroom mind schema context document.

    Args:
        schema_name: The schema the context conforms to (e.g. ``"manas"``).
        context_id: The context identifier (e.g. ``"ceo"``).

    Returns:
        Dict with ``schema_name``, ``context_id``, ``data`` (the JSON-LD
        document), and ``updated_at``, or an error dict if not found.
    """
    result = schema_storage.get_schema_context(schema_name, context_id)
    if result is None:
        return {"error": f"Schema context '{schema_name}/{context_id}' not found"}
    return result


@mcp.tool()
def list_schema_contexts(
    schema_name: str | None = None,
) -> list[dict[str, Any]]:
    """List stored schema contexts, optionally filtered by schema name.

    Args:
        schema_name: Optional filter — when provided only contexts for this
            schema are returned.

    Returns:
        List of summary records with ``schema_name``, ``context_id``, and
        ``updated_at``.
    """
    return schema_storage.list_schema_contexts(schema_name)


# ---------------------------------------------------------------------------
# MCP Prompts
# ---------------------------------------------------------------------------

@mcp.prompt()
def summarize_conversation(orchestration_id: str) -> str:
    """Generate a prompt that asks the model to summarise an orchestration conversation."""
    messages = storage.get_conversation(orchestration_id, limit=500)
    if not messages:
        return f"No messages found for orchestration '{orchestration_id}'."

    lines = [f"Summarise the following multi-agent conversation (orchestration {orchestration_id}):\n"]
    for msg in messages:
        lines.append(f"[{msg['role']}] {msg['agent_id']}: {msg['content']}")
    lines.append("\nProvide a concise summary covering key decisions, actions taken, and outcomes.")
    return "\n".join(lines)
