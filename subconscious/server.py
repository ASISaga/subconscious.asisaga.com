"""FastMCP server — multi-agent conversation persistence.

Exposes orchestration management, message persistence, and conversation
retrieval as MCP Tools and Resources.  Designed for use by Microsoft Agent
Framework orchestrations deployed on Foundry Agent Service.
"""

from __future__ import annotations

import logging
from typing import Any

from fastmcp import FastMCP

from subconscious import storage

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "Subconscious",
    instructions=(
        "Multi-agent conversation persistence server.  "
        "Persist and retrieve orchestration conversations from Azure Table Storage.  "
        "Use 'create_orchestration' to register a new orchestration, "
        "'persist_message' or 'persist_conversation_turn' to append messages, "
        "and 'get_conversation' to retrieve the full history by orchestration ID."
    ),
)


# ---------------------------------------------------------------------------
# MCP Resources
# ---------------------------------------------------------------------------

@mcp.resource("orchestration://{orchestration_id}")
def orchestration_resource(orchestration_id: str) -> str:
    """Return orchestration metadata and its full conversation history as JSON."""
    import json

    orch = storage.get_orchestration(orchestration_id)
    if orch is None:
        return json.dumps({"error": f"Orchestration '{orchestration_id}' not found"})
    messages = storage.get_conversation(orchestration_id)
    return json.dumps({**orch, "messages": messages})


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
    """List all known orchestrations, optionally filtered by status.

    Args:
        status: Filter by ``active``, ``completed``, or ``failed``.

    Returns:
        A list of orchestration summary records.
    """
    return storage.list_orchestrations(status)


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
    """Retrieve the full conversation for an orchestration.

    Args:
        orchestration_id: The orchestration whose conversation to retrieve.
        limit: Maximum number of messages to return (default 200).

    Returns:
        Dict with ``orchestration_id``, ``messages`` list, and ``total`` count.
    """
    messages = storage.get_conversation(orchestration_id, limit=limit)
    orch = storage.get_orchestration(orchestration_id)
    return {
        "orchestration_id": orchestration_id,
        "purpose": orch.get("purpose", "") if orch else "",
        "status": orch.get("status", "unknown") if orch else "unknown",
        "messages": messages,
        "total": len(messages),
    }


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
