"""Azure Table Storage operations for multi-agent conversation persistence.

Two tables are used:

* **Orchestrations** — one row per orchestration (PartitionKey ``orchestrations``).
* **Conversations** — one row per message (PartitionKey = *orchestration_id*).

Row-keys inside the Conversations table are zero-padded microsecond timestamps
so that messages sort in chronological order by default.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import time
from datetime import UTC, datetime
from typing import Any

from azure.core.exceptions import ResourceNotFoundError
from azure.data.tables import TableServiceClient

logger = logging.getLogger(__name__)

ORCHESTRATIONS_TABLE = "Orchestrations"
CONVERSATIONS_TABLE = "Conversations"
_PK_INDEX = "orchestrations"


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def _service_client() -> TableServiceClient:
    """Build a ``TableServiceClient`` from available connection settings."""
    conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING") or os.environ.get("AzureWebJobsStorage", "")
    return TableServiceClient.from_connection_string(conn_str)


def _ensure_tables(service: TableServiceClient) -> None:
    """Create both tables if they do not already exist."""
    for name in (ORCHESTRATIONS_TABLE, CONVERSATIONS_TABLE):
        try:
            service.create_table(name)
        except ResourceNotFoundError:
            pass
        except Exception:  # noqa: BLE001 — ResourceExistsError or HttpResponseError
            # Table already exists — safe to ignore
            pass


def _orchestrations_client():
    svc = _service_client()
    _ensure_tables(svc)
    return svc.get_table_client(ORCHESTRATIONS_TABLE)


def _conversations_client():
    svc = _service_client()
    _ensure_tables(svc)
    return svc.get_table_client(CONVERSATIONS_TABLE)


# ---------------------------------------------------------------------------
# Row-key generation
# ---------------------------------------------------------------------------

def _msg_row_key() -> str:
    """Return a chronologically-sortable row key: ``msg_<epoch_us>_<rand>``."""
    epoch_us = int(time.time() * 1_000_000)
    rand = secrets.token_hex(3)
    return f"msg_{epoch_us:020d}_{rand}"


# ---------------------------------------------------------------------------
# Orchestration CRUD
# ---------------------------------------------------------------------------

def create_orchestration(
    orchestration_id: str,
    purpose: str,
    agents: list[str] | None = None,
) -> dict[str, Any]:
    """Create a new orchestration record.  Returns the stored entity as a dict."""
    client = _orchestrations_client()
    now_iso = datetime.now(UTC).isoformat()
    entity: dict[str, Any] = {
        "PartitionKey": _PK_INDEX,
        "RowKey": orchestration_id,
        "Purpose": purpose,
        "Status": "active",
        "Agents": json.dumps(agents or []),
        "MessageCount": 0,
        "CreatedAt": now_iso,
        "UpdatedAt": now_iso,
    }
    client.upsert_entity(entity)
    logger.info("Created orchestration %s", orchestration_id)
    return _entity_to_orchestration(entity)


def get_orchestration(orchestration_id: str) -> dict[str, Any] | None:
    """Fetch a single orchestration by id.  Returns ``None`` if missing."""
    client = _orchestrations_client()
    try:
        entity = client.get_entity(partition_key=_PK_INDEX, row_key=orchestration_id)
        return _entity_to_orchestration(entity)
    except ResourceNotFoundError:
        return None


def list_orchestrations(status: str | None = None) -> list[dict[str, Any]]:
    """Return all orchestrations, optionally filtered by *status*."""
    client = _orchestrations_client()
    query = f"PartitionKey eq '{_PK_INDEX}'"
    if status:
        query += f" and Status eq '{status}'"
    entities = client.query_entities(query)
    return [_entity_to_orchestration(e) for e in entities]


def update_orchestration_status(
    orchestration_id: str,
    status: str,
    summary: str | None = None,
) -> dict[str, Any]:
    """Update the status (and optional summary) of an orchestration."""
    client = _orchestrations_client()
    now_iso = datetime.now(UTC).isoformat()
    try:
        entity = client.get_entity(partition_key=_PK_INDEX, row_key=orchestration_id)
    except ResourceNotFoundError as exc:
        raise ValueError(f"Orchestration '{orchestration_id}' not found") from exc

    entity["Status"] = status
    entity["UpdatedAt"] = now_iso
    if summary is not None:
        entity["Summary"] = summary
    client.upsert_entity(entity)
    return _entity_to_orchestration(entity)


# ---------------------------------------------------------------------------
# Conversation message CRUD
# ---------------------------------------------------------------------------

def persist_message(
    orchestration_id: str,
    agent_id: str,
    role: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append a single message to a conversation and bump the counter."""
    conv_client = _conversations_client()
    row_key = _msg_row_key()
    now_iso = datetime.now(UTC).isoformat()

    entity: dict[str, Any] = {
        "PartitionKey": orchestration_id,
        "RowKey": row_key,
        "AgentId": agent_id,
        "Role": role,
        "Content": content,
        "Metadata": json.dumps(metadata or {}),
        "CreatedAt": now_iso,
    }
    conv_client.upsert_entity(entity)

    # Increment message count on the orchestration (best-effort)
    _increment_message_count(orchestration_id)

    return {
        "orchestration_id": orchestration_id,
        "sequence": row_key,
        "agent_id": agent_id,
        "role": role,
        "created_at": now_iso,
    }


def persist_messages(
    orchestration_id: str,
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Persist multiple messages in one go and return their metadata."""
    results: list[dict[str, Any]] = []
    for msg in messages:
        result = persist_message(
            orchestration_id=orchestration_id,
            agent_id=msg["agent_id"],
            role=msg["role"],
            content=msg["content"],
            metadata=msg.get("metadata"),
        )
        results.append(result)
    return results


def get_conversation(
    orchestration_id: str,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Return all messages for an orchestration in chronological order."""
    client = _conversations_client()
    query = f"PartitionKey eq '{orchestration_id}'"
    entities = list(client.query_entities(query))
    entities.sort(key=lambda e: e.get("RowKey", ""))
    if limit:
        entities = entities[:limit]
    return [_entity_to_message(e) for e in entities]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _increment_message_count(orchestration_id: str) -> None:
    """Best-effort increment of the message counter on an orchestration row."""
    client = _orchestrations_client()
    try:
        entity = client.get_entity(partition_key=_PK_INDEX, row_key=orchestration_id)
        entity["MessageCount"] = int(entity.get("MessageCount", 0)) + 1
        entity["UpdatedAt"] = datetime.now(UTC).isoformat()
        client.upsert_entity(entity)
    except ResourceNotFoundError:
        pass


def _entity_to_orchestration(entity: dict[str, Any]) -> dict[str, Any]:
    """Normalise an Azure Table entity into a clean orchestration dict."""
    agents_raw = entity.get("Agents", "[]")
    agents = json.loads(agents_raw) if isinstance(agents_raw, str) else agents_raw
    return {
        "orchestration_id": entity.get("RowKey", ""),
        "purpose": entity.get("Purpose", ""),
        "status": entity.get("Status", "active"),
        "agents": agents,
        "message_count": int(entity.get("MessageCount", 0)),
        "summary": entity.get("Summary", ""),
        "created_at": entity.get("CreatedAt", ""),
        "updated_at": entity.get("UpdatedAt", ""),
    }


def _entity_to_message(entity: dict[str, Any]) -> dict[str, Any]:
    """Normalise an Azure Table entity into a clean message dict."""
    meta_raw = entity.get("Metadata", "{}")
    metadata = json.loads(meta_raw) if isinstance(meta_raw, str) else meta_raw
    return {
        "orchestration_id": entity.get("PartitionKey", ""),
        "sequence": entity.get("RowKey", ""),
        "agent_id": entity.get("AgentId", ""),
        "role": entity.get("Role", ""),
        "content": entity.get("Content", ""),
        "metadata": metadata,
        "created_at": entity.get("CreatedAt", ""),
    }
