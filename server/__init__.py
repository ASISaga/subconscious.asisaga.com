"""FastMCP server — multi-agent conversation persistence and schema context management.

The FastMCP instance ``mcp`` is created here along with the ``Conversations``
``FastMCPApp``.  Importing this package triggers registration of all MCP tools,
resources, and prompts defined in the sub-modules.

Sub-modules
-----------
* :mod:`server.tools` — MCP tools (orchestration lifecycle, message persistence,
  conversation retrieval, schema management).
* :mod:`server.resources` — MCP resources (orchestration, schema, schema-context).
* :mod:`server.prompts` — MCP prompts (summarize_conversation).

JSON-LD helpers
---------------
:func:`_orchestration_to_jsonld`, :func:`_message_to_jsonld`, and
:func:`_conversation_to_jsonld` are re-exported here so that the data-endpoint
blueprints can use them without importing individual sub-modules.
"""

from __future__ import annotations

import logging
from typing import Any

from fastmcp import FastMCP, FastMCPApp

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema.org JSON-LD annotation helpers (shared between tools and blueprints)
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
        "Use the dedicated semantic mind-layer tools to read and write CXO agent state: "
        "'get_chitta'/'set_chitta' (pure intelligence), "
        "'get_ahankara'/'set_ahankara' (identity and ego), "
        "'get_buddhi'/'set_buddhi' (domain intellect), "
        "'get_action_plan'/'set_action_plan' (strategic action plan), "
        "'get_manas'/'set_manas' (working memory and active focus), "
        "'get_integrity'/'set_integrity' (integrity register), "
        "'get_responsibilities'/'set_responsibilities' (role responsibilities — supply agent_id and role), "
        "'get_entity_content'/'set_entity_content' (mutable entity perspective — supply agent_id and entity), "
        "'get_entity_context'/'set_entity_context' (immutable entity perspective — supply agent_id and entity).  "
        "All schema-context and mind-layer tools accept an optional 'company_id' parameter "
        "for multi-company/product scoping (provision for future scaling).  "
        "Use 'show_conversations' to open the interactive conversation browser UI."
    ),
)

# ---------------------------------------------------------------------------
# FastMCPApp — Conversations App
# ---------------------------------------------------------------------------

conversations_app = FastMCPApp("Conversations")

# ---------------------------------------------------------------------------
# Register sub-modules — importing each triggers decorator registration
# ---------------------------------------------------------------------------

from server import prompts as _prompts  # noqa: E402, F401
from server import resources as _resources  # noqa: E402, F401
from server import tools as _tools  # noqa: E402, F401

# Link the Conversations App to the MCP server (must run after tools are defined)
mcp.add_provider(conversations_app)

__all__ = [
    "mcp",
    "conversations_app",
    "_orchestration_to_jsonld",
    "_message_to_jsonld",
    "_conversation_to_jsonld",
]
