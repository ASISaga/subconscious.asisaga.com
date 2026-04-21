"""MCP tools — orchestration lifecycle, message persistence, conversation retrieval,
schema management, and Conversations App tools.
"""

from __future__ import annotations

from typing import Any

from server import _conversation_to_jsonld, _orchestration_to_jsonld, conversations_app, mcp
from storage import conversations as storage_conv
from storage import schemas as schema_storage

# ---------------------------------------------------------------------------
# Dimension resolution — maps agent-centric state keys to (schema_name, context_id)
# ---------------------------------------------------------------------------

#: Direct (non-prefixed) dimension names that map to a top-level schema.
_DIRECT_DIMENSIONS: dict[str, str] = {
    "manas": "manas",
    "buddhi": "buddhi",
    "action-plan": "action-plan",
    "ahankara": "ahankara",
    "chitta": "chitta",
    "integrity": "integrity",
}

#: Prefix-based dimension names — key is the path prefix, value is the schema name.
#: The remainder after the prefix becomes the sub-key appended to the agent_id.
_PREFIX_DIMENSIONS: dict[str, str] = {
    "responsibilities/": "responsibilities",
    "manas/content/": "entity-content",
    "manas/context/": "entity-context",
}


def _resolve_dimension(agent_id: str, dimension: str) -> tuple[str, str]:
    """Resolve an agent-centric *dimension* key to a ``(schema_name, context_id)`` pair.

    Supported dimension formats:

    * ``"manas"`` → ``("manas", agent_id)``
    * ``"buddhi"`` → ``("buddhi", agent_id)``
    * ``"action-plan"`` → ``("action-plan", agent_id)``
    * ``"ahankara"`` → ``("ahankara", agent_id)``
    * ``"chitta"`` → ``("chitta", agent_id)``
    * ``"integrity"`` → ``("integrity", agent_id)``
    * ``"responsibilities/{name}"`` → ``("responsibilities", "{agent_id}/{name}")``
    * ``"manas/content/{entity}"`` → ``("entity-content", "{agent_id}/{entity}")``
    * ``"manas/context/{entity}"`` → ``("entity-context", "{agent_id}/{entity}")``

    Args:
        agent_id: The CXO agent identifier (e.g. ``"ceo"``).
        dimension: The dimension path string (see above).

    Returns:
        ``(schema_name, context_id)`` tuple.

    Raises:
        ValueError: When *dimension* is not a recognised format.
    """
    if dimension in _DIRECT_DIMENSIONS:
        return (_DIRECT_DIMENSIONS[dimension], agent_id)
    for prefix, schema_name in _PREFIX_DIMENSIONS.items():
        if dimension.startswith(prefix):
            sub_key = dimension[len(prefix):]
            return (schema_name, f"{agent_id}/{sub_key}")
    known = list(_DIRECT_DIMENSIONS) + [f"{p}<key>" for p in _PREFIX_DIMENSIONS]
    raise ValueError(
        f"Unknown dimension '{dimension}'. "
        f"Supported formats: {known}"
    )




@conversations_app.tool()
def fetch_orchestrations(status: str | None = None) -> list[dict[str, Any]]:
    """Load all orchestrations as Schema.org Action JSON-LD documents.

    Called by the Conversations UI to populate the orchestration list.

    Args:
        status: Optional filter — ``active``, ``completed``, or ``failed``.

    Returns:
        List of Schema.org Action JSON-LD documents.
    """
    raw = storage_conv.list_orchestrations(status)
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
    msgs = storage_conv.get_conversation(orchestration_id)
    orch = storage_conv.get_orchestration(orchestration_id)
    return _conversation_to_jsonld(orchestration_id, msgs, orch)


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
    from server import _SCHEMA_ORG
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
    return storage_conv.create_orchestration(orchestration_id, purpose, agents)


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
    return storage_conv.update_orchestration_status(orchestration_id, "completed", summary)


@mcp.tool()
def list_orchestrations(status: str | None = None) -> list[dict[str, Any]]:
    """List all known orchestrations as Schema.org Action JSON-LD documents.

    Args:
        status: Filter by ``active``, ``completed``, or ``failed``.

    Returns:
        A list of Schema.org Action JSON-LD orchestration records.
    """
    raw = storage_conv.list_orchestrations(status)
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
    return storage_conv.persist_message(orchestration_id, agent_id, role, content, metadata)


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
    results = storage_conv.persist_messages(orchestration_id, messages)
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
    messages = storage_conv.get_conversation(orchestration_id, limit=limit)
    orch = storage_conv.get_orchestration(orchestration_id)
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
    company_id: str | None = None,
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
        company_id: Optional company scope (e.g. ``"asisaga"``).  Provision
            for multi-company/product scaling — when supplied the row is stored
            under ``{company_id}/{context_id}``.

    Returns:
        Confirmation with ``schema_name``, ``context_id``, and ``updated_at``.
    """
    return schema_storage.store_schema_context(schema_name, context_id, data, company_id=company_id)


@mcp.tool()
def get_schema_context(
    schema_name: str,
    context_id: str,
    company_id: str | None = None,
) -> dict[str, Any]:
    """Retrieve a stored boardroom mind schema context document.

    Args:
        schema_name: The schema the context conforms to (e.g. ``"manas"``).
        context_id: The context identifier (e.g. ``"ceo"``).
        company_id: Optional company scope.  Must match the value used when
            the context was stored.  Provision for multi-company/product scaling.

    Returns:
        Dict with ``schema_name``, ``context_id``, ``data`` (the JSON-LD
        document), and ``updated_at``, or an error dict if not found.
    """
    result = schema_storage.get_schema_context(schema_name, context_id, company_id=company_id)
    if result is None:
        return {"error": f"Schema context '{schema_name}/{context_id}' not found"}
    return result


@mcp.tool()
def list_schema_contexts(
    schema_name: str | None = None,
    company_id: str | None = None,
) -> list[dict[str, Any]]:
    """List stored schema contexts, optionally filtered by schema name and company.

    Args:
        schema_name: Optional filter — when provided only contexts for this
            schema are returned.
        company_id: Optional company scope filter.  Provision for
            multi-company/product scaling.

    Returns:
        List of summary records with ``schema_name``, ``context_id``, and
        ``updated_at``.
    """
    return schema_storage.list_schema_contexts(schema_name, company_id=company_id)


@mcp.tool()
def initialize_schema_contexts(
    force: bool = False,
    company_id: str | None = None,
) -> dict[str, Any]:
    """Initialize schema-context rows from files in the repository mind directory.

    Args:
        force: When ``True``, writes mind data even if rows already exist.
            Default ``False`` performs one-time bootstrap only when the table
            is empty.
        company_id: Optional company scope applied to every seeded row.
            Provision for multi-company/product scaling.

    Returns:
        Initialization result with status, seeded row count, and source path.
    """
    return schema_storage.initialize_schema_contexts_from_mind(force=force, company_id=company_id)


# ---------------------------------------------------------------------------
# MCP Tools — CXO agent state (read/write atomic mind states by semantic layer)
# ---------------------------------------------------------------------------
#
# Each of the four primary mind layers — Chitta, Ahankara, Buddhi, and Manas —
# has a dedicated get/set pair.  Sub-dimensions of Manas (action-plan, entity
# content/context perspectives, responsibilities, and integrity) also have
# dedicated tools.  All tools accept an optional ``company_id`` for
# multi-company/product scoping.
# ---------------------------------------------------------------------------


def _missing_state_error(agent_id: str, layer: str, company_id: str | None) -> dict[str, Any]:
    """Return a consistent error dict for a missing mind-state row."""
    suffix = f" (company '{company_id}')" if company_id else ""
    return {"error": f"No {layer} state found for agent '{agent_id}'{suffix}"}


# ── Chitta — pure intelligence ───────────────────────────────────────────────

@mcp.tool()
def get_chitta(agent_id: str, company_id: str | None = None) -> dict[str, Any]:
    """Read the Chitta (pure intelligence) state for a CXO agent.

    Chitta holds the agent's deepest, immutable intelligence — core values,
    universal principles, and the highest level of consciousness.  It
    conforms to the ``chitta`` JSON Schema (see ``get_schema("chitta")``).

    Args:
        agent_id: Unique CXO agent identifier (e.g. ``"ceo"``, ``"cfo"``).
        company_id: Optional company scope (e.g. ``"asisaga"``).  Provision
            for multi-company/product scaling.

    Returns:
        The stored Chitta document, or an error dict if not found.
    """
    result = schema_storage.get_schema_context("chitta", agent_id, company_id=company_id)
    if result is None:
        return _missing_state_error(agent_id, "Chitta", company_id)
    return result


@mcp.tool()
def set_chitta(
    agent_id: str,
    data: dict[str, Any],
    company_id: str | None = None,
) -> dict[str, Any]:
    """Write the Chitta (pure intelligence) state for a CXO agent.

    Persists *data* as the agent's Chitta document conforming to the
    ``chitta`` JSON Schema (see ``get_schema("chitta")``).

    Args:
        agent_id: Unique CXO agent identifier (e.g. ``"ceo"``, ``"cfo"``).
        data: The JSON-LD Chitta document to persist.
        company_id: Optional company scope (e.g. ``"asisaga"``).  Provision
            for multi-company/product scaling.

    Returns:
        Confirmation with ``schema_name``, ``context_id``, and ``updated_at``.
    """
    return schema_storage.store_schema_context("chitta", agent_id, data, company_id=company_id)


# ── Ahankara — identity and ego ──────────────────────────────────────────────

@mcp.tool()
def get_ahankara(agent_id: str, company_id: str | None = None) -> dict[str, Any]:
    """Read the Ahankara (identity and ego) state for a CXO agent.

    Ahankara defines the agent's sense of self — role identity, personal
    mission, and the ego structure that shapes decision-making.  It conforms
    to the ``ahankara`` JSON Schema (see ``get_schema("ahankara")``).

    Args:
        agent_id: Unique CXO agent identifier (e.g. ``"ceo"``, ``"cfo"``).
        company_id: Optional company scope (e.g. ``"asisaga"``).  Provision
            for multi-company/product scaling.

    Returns:
        The stored Ahankara document, or an error dict if not found.
    """
    result = schema_storage.get_schema_context("ahankara", agent_id, company_id=company_id)
    if result is None:
        return _missing_state_error(agent_id, "Ahankara", company_id)
    return result


@mcp.tool()
def set_ahankara(
    agent_id: str,
    data: dict[str, Any],
    company_id: str | None = None,
) -> dict[str, Any]:
    """Write the Ahankara (identity and ego) state for a CXO agent.

    Persists *data* as the agent's Ahankara document conforming to the
    ``ahankara`` JSON Schema (see ``get_schema("ahankara")``).

    Args:
        agent_id: Unique CXO agent identifier (e.g. ``"ceo"``, ``"cfo"``).
        data: The JSON-LD Ahankara document to persist.
        company_id: Optional company scope (e.g. ``"asisaga"``).  Provision
            for multi-company/product scaling.

    Returns:
        Confirmation with ``schema_name``, ``context_id``, and ``updated_at``.
    """
    return schema_storage.store_schema_context("ahankara", agent_id, data, company_id=company_id)


# ── Buddhi — domain intellect ────────────────────────────────────────────────

@mcp.tool()
def get_buddhi(agent_id: str, company_id: str | None = None) -> dict[str, Any]:
    """Read the Buddhi (domain intellect) state for a CXO agent.

    Buddhi captures the agent's domain knowledge, reasoning frameworks, and
    strategic intelligence — the discriminative faculty applied to the
    agent's area of expertise.  It conforms to the ``buddhi`` JSON Schema
    (see ``get_schema("buddhi")``).

    Args:
        agent_id: Unique CXO agent identifier (e.g. ``"ceo"``, ``"cfo"``).
        company_id: Optional company scope (e.g. ``"asisaga"``).  Provision
            for multi-company/product scaling.

    Returns:
        The stored Buddhi document, or an error dict if not found.
    """
    result = schema_storage.get_schema_context("buddhi", agent_id, company_id=company_id)
    if result is None:
        return _missing_state_error(agent_id, "Buddhi", company_id)
    return result


@mcp.tool()
def set_buddhi(
    agent_id: str,
    data: dict[str, Any],
    company_id: str | None = None,
) -> dict[str, Any]:
    """Write the Buddhi (domain intellect) state for a CXO agent.

    Persists *data* as the agent's Buddhi document conforming to the
    ``buddhi`` JSON Schema (see ``get_schema("buddhi")``).

    Args:
        agent_id: Unique CXO agent identifier (e.g. ``"ceo"``, ``"cfo"``).
        data: The JSON-LD Buddhi document to persist.
        company_id: Optional company scope (e.g. ``"asisaga"``).  Provision
            for multi-company/product scaling.

    Returns:
        Confirmation with ``schema_name``, ``context_id``, and ``updated_at``.
    """
    return schema_storage.store_schema_context("buddhi", agent_id, data, company_id=company_id)


# ── Action Plan — Buddhi action plan ─────────────────────────────────────────

@mcp.tool()
def get_action_plan(agent_id: str, company_id: str | None = None) -> dict[str, Any]:
    """Read the Action Plan state for a CXO agent.

    The Action Plan is the agent's Buddhi-derived strategic plan toward the
    company purpose — the concrete roadmap derived from domain intellect.
    It conforms to the ``action-plan`` JSON Schema
    (see ``get_schema("action-plan")``).

    Args:
        agent_id: Unique CXO agent identifier (e.g. ``"ceo"``, ``"cfo"``).
        company_id: Optional company scope (e.g. ``"asisaga"``).  Provision
            for multi-company/product scaling.

    Returns:
        The stored Action Plan document, or an error dict if not found.
    """
    result = schema_storage.get_schema_context("action-plan", agent_id, company_id=company_id)
    if result is None:
        return _missing_state_error(agent_id, "Action Plan", company_id)
    return result


@mcp.tool()
def set_action_plan(
    agent_id: str,
    data: dict[str, Any],
    company_id: str | None = None,
) -> dict[str, Any]:
    """Write the Action Plan state for a CXO agent.

    Persists *data* as the agent's Action Plan document conforming to the
    ``action-plan`` JSON Schema (see ``get_schema("action-plan")``).

    Args:
        agent_id: Unique CXO agent identifier (e.g. ``"ceo"``, ``"cfo"``).
        data: The JSON-LD Action Plan document to persist.
        company_id: Optional company scope (e.g. ``"asisaga"``).  Provision
            for multi-company/product scaling.

    Returns:
        Confirmation with ``schema_name``, ``context_id``, and ``updated_at``.
    """
    return schema_storage.store_schema_context("action-plan", agent_id, data, company_id=company_id)


# ── Manas — working memory and active focus ───────────────────────────────────

@mcp.tool()
def get_manas(agent_id: str, company_id: str | None = None) -> dict[str, Any]:
    """Read the Manas (working memory and active focus) state for a CXO agent.

    Manas is the agent's active working mind — current focus, open tasks,
    and in-progress deliberations.  It conforms to the ``manas`` JSON Schema
    (see ``get_schema("manas")``).

    Args:
        agent_id: Unique CXO agent identifier (e.g. ``"ceo"``, ``"cfo"``).
        company_id: Optional company scope (e.g. ``"asisaga"``).  Provision
            for multi-company/product scaling.

    Returns:
        The stored Manas document, or an error dict if not found.
    """
    result = schema_storage.get_schema_context("manas", agent_id, company_id=company_id)
    if result is None:
        return _missing_state_error(agent_id, "Manas", company_id)
    return result


@mcp.tool()
def set_manas(
    agent_id: str,
    data: dict[str, Any],
    company_id: str | None = None,
) -> dict[str, Any]:
    """Write the Manas (working memory and active focus) state for a CXO agent.

    Persists *data* as the agent's Manas document conforming to the
    ``manas`` JSON Schema (see ``get_schema("manas")``).

    Args:
        agent_id: Unique CXO agent identifier (e.g. ``"ceo"``, ``"cfo"``).
        data: The JSON-LD Manas document to persist.
        company_id: Optional company scope (e.g. ``"asisaga"``).  Provision
            for multi-company/product scaling.

    Returns:
        Confirmation with ``schema_name``, ``context_id``, and ``updated_at``.
    """
    return schema_storage.store_schema_context("manas", agent_id, data, company_id=company_id)


# ── Integrity — integrity register ───────────────────────────────────────────

@mcp.tool()
def get_integrity(agent_id: str, company_id: str | None = None) -> dict[str, Any]:
    """Read the Integrity register for a CXO agent.

    The Integrity register records the agent's commitments, value alignment
    history, and integrity assessments.  It conforms to the ``integrity``
    JSON Schema (see ``get_schema("integrity")``).

    Args:
        agent_id: Unique CXO agent identifier (e.g. ``"ceo"``, ``"cfo"``).
        company_id: Optional company scope (e.g. ``"asisaga"``).  Provision
            for multi-company/product scaling.

    Returns:
        The stored Integrity document, or an error dict if not found.
    """
    result = schema_storage.get_schema_context("integrity", agent_id, company_id=company_id)
    if result is None:
        return _missing_state_error(agent_id, "Integrity", company_id)
    return result


@mcp.tool()
def set_integrity(
    agent_id: str,
    data: dict[str, Any],
    company_id: str | None = None,
) -> dict[str, Any]:
    """Write the Integrity register for a CXO agent.

    Persists *data* as the agent's Integrity document conforming to the
    ``integrity`` JSON Schema (see ``get_schema("integrity")``).

    Args:
        agent_id: Unique CXO agent identifier (e.g. ``"ceo"``, ``"cfo"``).
        data: The JSON-LD Integrity document to persist.
        company_id: Optional company scope (e.g. ``"asisaga"``).  Provision
            for multi-company/product scaling.

    Returns:
        Confirmation with ``schema_name``, ``context_id``, and ``updated_at``.
    """
    return schema_storage.store_schema_context("integrity", agent_id, data, company_id=company_id)


# ── Responsibilities — role responsibilities ──────────────────────────────────

@mcp.tool()
def get_responsibilities(
    agent_id: str,
    role: str,
    company_id: str | None = None,
) -> dict[str, Any]:
    """Read a role-responsibilities document for a CXO agent.

    Each agent carries responsibility documents for each of their active
    roles — typically ``"entrepreneur"``, ``"manager"``, and
    ``"domain-expert"``.  The document conforms to the
    ``responsibilities`` JSON Schema (see ``get_schema("responsibilities")``).

    Args:
        agent_id: Unique CXO agent identifier (e.g. ``"ceo"``, ``"cfo"``).
        role: The role name (e.g. ``"entrepreneur"``, ``"manager"``,
            ``"domain-expert"``).
        company_id: Optional company scope (e.g. ``"asisaga"``).  Provision
            for multi-company/product scaling.

    Returns:
        The stored Responsibilities document, or an error dict if not found.
    """
    context_id = f"{agent_id}/{role}"
    result = schema_storage.get_schema_context("responsibilities", context_id, company_id=company_id)
    if result is None:
        suffix = f" (company '{company_id}')" if company_id else ""
        return {"error": f"No Responsibilities state found for agent '{agent_id}' role '{role}'{suffix}"}
    return result


@mcp.tool()
def set_responsibilities(
    agent_id: str,
    role: str,
    data: dict[str, Any],
    company_id: str | None = None,
) -> dict[str, Any]:
    """Write a role-responsibilities document for a CXO agent.

    Persists *data* as the agent's responsibilities for *role*, conforming
    to the ``responsibilities`` JSON Schema
    (see ``get_schema("responsibilities")``).

    Args:
        agent_id: Unique CXO agent identifier (e.g. ``"ceo"``, ``"cfo"``).
        role: The role name (e.g. ``"entrepreneur"``, ``"manager"``,
            ``"domain-expert"``).
        data: The JSON-LD Responsibilities document to persist.
        company_id: Optional company scope (e.g. ``"asisaga"``).  Provision
            for multi-company/product scaling.

    Returns:
        Confirmation with ``schema_name``, ``context_id``, and ``updated_at``.
    """
    context_id = f"{agent_id}/{role}"
    return schema_storage.store_schema_context("responsibilities", context_id, data, company_id=company_id)


# ── Entity content — mutable entity perspective (Manas) ──────────────────────

@mcp.tool()
def get_entity_content(
    agent_id: str,
    entity: str,
    company_id: str | None = None,
) -> dict[str, Any]:
    """Read a mutable entity content perspective from an agent's Manas.

    Entity content perspectives capture the agent's current, mutable view
    of a specific entity (e.g. ``"company"``, ``"business-infinity"``).
    They conforms to the ``entity-content`` JSON Schema
    (see ``get_schema("entity-content")``).

    Args:
        agent_id: Unique CXO agent identifier (e.g. ``"ceo"``, ``"cfo"``).
        entity: The entity identifier (e.g. ``"company"``,
            ``"business-infinity"``).
        company_id: Optional company scope (e.g. ``"asisaga"``).  Provision
            for multi-company/product scaling.

    Returns:
        The stored entity content document, or an error dict if not found.
    """
    context_id = f"{agent_id}/{entity}"
    result = schema_storage.get_schema_context("entity-content", context_id, company_id=company_id)
    if result is None:
        suffix = f" (company '{company_id}')" if company_id else ""
        return {"error": f"No entity content state found for agent '{agent_id}' entity '{entity}'{suffix}"}
    return result


@mcp.tool()
def set_entity_content(
    agent_id: str,
    entity: str,
    data: dict[str, Any],
    company_id: str | None = None,
) -> dict[str, Any]:
    """Write a mutable entity content perspective into an agent's Manas.

    Persists *data* as the agent's mutable perspective on *entity*,
    conforming to the ``entity-content`` JSON Schema
    (see ``get_schema("entity-content")``).

    Args:
        agent_id: Unique CXO agent identifier (e.g. ``"ceo"``, ``"cfo"``).
        entity: The entity identifier (e.g. ``"company"``,
            ``"business-infinity"``).
        data: The JSON-LD entity content document to persist.
        company_id: Optional company scope (e.g. ``"asisaga"``).  Provision
            for multi-company/product scaling.

    Returns:
        Confirmation with ``schema_name``, ``context_id``, and ``updated_at``.
    """
    context_id = f"{agent_id}/{entity}"
    return schema_storage.store_schema_context("entity-content", context_id, data, company_id=company_id)


# ── Entity context — immutable entity perspective (Manas) ────────────────────

@mcp.tool()
def get_entity_context(
    agent_id: str,
    entity: str,
    company_id: str | None = None,
) -> dict[str, Any]:
    """Read an immutable entity context perspective from an agent's Manas.

    Entity context perspectives capture the agent's stable, immutable
    understanding of a specific entity (e.g. ``"company"``,
    ``"business-infinity"``).  They conform to the ``entity-context`` JSON
    Schema (see ``get_schema("entity-context")``).

    Args:
        agent_id: Unique CXO agent identifier (e.g. ``"ceo"``, ``"cfo"``).
        entity: The entity identifier (e.g. ``"company"``,
            ``"business-infinity"``).
        company_id: Optional company scope (e.g. ``"asisaga"``).  Provision
            for multi-company/product scaling.

    Returns:
        The stored entity context document, or an error dict if not found.
    """
    context_id = f"{agent_id}/{entity}"
    result = schema_storage.get_schema_context("entity-context", context_id, company_id=company_id)
    if result is None:
        suffix = f" (company '{company_id}')" if company_id else ""
        return {"error": f"No entity context state found for agent '{agent_id}' entity '{entity}'{suffix}"}
    return result


@mcp.tool()
def set_entity_context(
    agent_id: str,
    entity: str,
    data: dict[str, Any],
    company_id: str | None = None,
) -> dict[str, Any]:
    """Write an immutable entity context perspective into an agent's Manas.

    Persists *data* as the agent's immutable understanding of *entity*,
    conforming to the ``entity-context`` JSON Schema
    (see ``get_schema("entity-context")``).

    Args:
        agent_id: Unique CXO agent identifier (e.g. ``"ceo"``, ``"cfo"``).
        entity: The entity identifier (e.g. ``"company"``,
            ``"business-infinity"``).
        data: The JSON-LD entity context document to persist.
        company_id: Optional company scope (e.g. ``"asisaga"``).  Provision
            for multi-company/product scaling.

    Returns:
        Confirmation with ``schema_name``, ``context_id``, and ``updated_at``.
    """
    context_id = f"{agent_id}/{entity}"
    return schema_storage.store_schema_context("entity-context", context_id, data, company_id=company_id)
