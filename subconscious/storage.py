"""Azure Table Storage operations for BoardroomMemory."""

from __future__ import annotations

import datetime
import logging
import os
from typing import Any

from azure.core.exceptions import ResourceNotFoundError
from azure.data.tables import TableServiceClient

logger = logging.getLogger(__name__)

TABLE_NAME = "BoardroomMemory"
_PARTITION_KEY_EVENTS = "StrategicEvent"
_PARTITION_KEY_STATE = "BoardroomState"

# Maximum millisecond value for a representable datetime (9999-12-31 23:59:59.999 UTC)
_MAX_TIMESTAMP_MS = 253402300799999


def _table_client():
    """Return a TableClient for the BoardroomMemory table."""
    conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING") or os.environ.get(
        "AzureWebJobsStorage", ""
    )
    service = TableServiceClient.from_connection_string(conn_str)
    return service.get_table_client(TABLE_NAME)


def _inverted_row_key() -> str:
    """Return an inverted-timestamp RowKey that sorts latest-first lexicographically."""
    now_ms = int(datetime.datetime.now(datetime.UTC).timestamp() * 1000)
    return str(_MAX_TIMESTAMP_MS - now_ms).zfill(16)


def get_boardroom_state() -> dict[str, Any]:
    """Return the latest Resonance Score and North Star goal from BoardroomMemory."""
    client = _table_client()
    try:
        entity = client.get_entity(
            partition_key=_PARTITION_KEY_STATE, row_key="NorthStar"
        )
        return {
            "north_star": entity.get("Goal", ""),
            "resonance_score": float(entity.get("ResonanceScore", 0.0)),
            "last_updated": entity.get("LastUpdated", ""),
        }
    except ResourceNotFoundError:
        return {"north_star": "", "resonance_score": 0.0, "last_updated": ""}


def record_event(
    agent_id: str,
    event_type: str,
    content: str,
    resonance_score: float,
) -> dict[str, Any]:
    """Write a strategic event to BoardroomMemory with an inverted timestamp RowKey."""
    client = _table_client()
    row_key = _inverted_row_key()
    now_iso = datetime.datetime.now(datetime.UTC).isoformat()

    event_entity: dict[str, Any] = {
        "PartitionKey": _PARTITION_KEY_EVENTS,
        "RowKey": row_key,
        "AgentId": agent_id,
        "EventType": event_type,
        "Content": content,
        "ResonanceScore": resonance_score,
        "Timestamp": now_iso,
    }
    client.upsert_entity(event_entity)

    # Keep the rolling BoardroomState row current
    state_entity: dict[str, Any] = {
        "PartitionKey": _PARTITION_KEY_STATE,
        "RowKey": "NorthStar",
        "ResonanceScore": resonance_score,
        "LastUpdated": now_iso,
        "LastEventType": event_type,
        "LastAgentId": agent_id,
    }
    client.upsert_entity(state_entity)

    return {"row_key": row_key, "status": "recorded", "timestamp": now_iso}
