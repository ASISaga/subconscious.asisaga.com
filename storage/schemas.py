"""Schema context persistence — serve boardroom mind schemas and store/retrieve JSON-LD contexts.

Two concerns are handled here:

1. **Schema definitions** — the canonical JSON Schema files from
   ``boardroom/mind/schemas/`` are loaded from disk and exposed as read-only
   artefacts via :func:`get_schema` and :func:`list_schemas`.

2. **Schema contexts** — JSON-LD documents that conform to a mind schema
   (e.g. an agent's Buddhi or Manas file) are persisted to and retrieved from
   Azure Table Storage via the ``SchemaContexts`` table.

Table layout for **SchemaContexts**:

* ``PartitionKey``: schema name (e.g. ``manas``, ``buddhi``, ``chitta``).
* ``RowKey``: context identifier (e.g. agent id ``ceo``, or compound key
  ``ceo/company`` for entity perspectives).
* ``Content``: JSON-serialised JSON-LD document.
* ``UpdatedAt``: ISO-8601 timestamp of the last write.

Demo-data fallback
------------------
When no Azure Storage connection string is configured the module falls back to
loading read-only demo contexts from Schema.org JSON-LD files in the
``data/schema_contexts/`` directory.  Filenames follow the convention
``<schema>-<context_id>.json`` (e.g. ``manas-ceo.json``).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from azure.core.exceptions import ResourceNotFoundError
from azure.data.tables import TableServiceClient

logger = logging.getLogger(__name__)

SCHEMA_CONTEXTS_TABLE = "SchemaContexts"

# ---------------------------------------------------------------------------
# Schema registry — maps canonical name → filename in boardroom/mind/schemas/
# ---------------------------------------------------------------------------

#: Ordered mapping of schema names to their JSON Schema filenames.
SCHEMA_REGISTRY: dict[str, str] = {
    "manas": "manas.schema.json",
    "buddhi": "buddhi.schema.json",
    "ahankara": "ahankara.schema.json",
    "chitta": "chitta.schema.json",
    "action-plan": "action-plan.schema.json",
    "entity-context": "entity-context.schema.json",
    "entity-content": "entity-content.schema.json",
    "responsibilities": "responsibilities.schema.json",
    "integrity": "integrity.schema.json",
}


# ---------------------------------------------------------------------------
# Demo-data helpers (file-based fallback)
# ---------------------------------------------------------------------------

def _storage_conn_str() -> str:
    return (
        os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        or os.environ.get("AzureWebJobsStorage", "")
    )


def _use_demo_data() -> bool:
    """Return ``True`` when no real Azure Storage connection string is configured."""
    return not _storage_conn_str()


def _demo_schema_contexts_dir() -> Path:
    override = os.environ.get("DEMO_DATA_DIR")
    if override:
        return Path(override) / "schema_contexts"
    return Path(__file__).parent.parent / "data" / "schema_contexts"


def _load_demo_schema_context(schema_name: str, context_id: str) -> dict[str, Any] | None:
    """Load a single demo schema context from a JSON-LD file.

    Looks for ``<schema_name>-<context_id>.json`` in the demo contexts directory.
    Falls back to scanning all files for a matching ``identifier``.
    """
    data_dir = _demo_schema_contexts_dir()
    if not data_dir.exists():
        return None
    # Primary: conventional filename
    primary = data_dir / f"{schema_name}-{context_id}.json"
    if primary.exists():
        try:
            doc = json.loads(primary.read_text(encoding="utf-8"))
            return {
                "schema_name": schema_name,
                "context_id": context_id,
                "data": doc,
                "updated_at": doc.get("dateModified", ""),
            }
        except (json.JSONDecodeError, OSError, KeyError) as exc:
            logger.warning("Failed to load demo context %s: %s", primary.name, exc)
    # Fallback: scan all files
    for path in data_dir.glob("*.json"):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
            schema_key = doc.get("mind:schema", "") or ""
            ctx_id = doc.get("identifier", "")
            if schema_key == schema_name and ctx_id == context_id:
                return {
                    "schema_name": schema_name,
                    "context_id": context_id,
                    "data": doc,
                    "updated_at": doc.get("dateModified", ""),
                }
        except (json.JSONDecodeError, OSError, KeyError) as exc:
            logger.warning("Failed to scan demo context %s: %s", path.name, exc)
    return None


def _list_demo_schema_contexts(schema_name: str | None = None) -> list[dict[str, Any]]:
    """List demo schema contexts, optionally filtered by schema name."""
    data_dir = _demo_schema_contexts_dir()
    if not data_dir.exists():
        return []
    results: list[dict[str, Any]] = []
    for path in sorted(data_dir.glob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
            schema_key = doc.get("mind:schema", "")
            ctx_id = doc.get("identifier", "")
            if schema_name and schema_key != schema_name:
                continue
            results.append({
                "schema_name": schema_key,
                "context_id": ctx_id,
                "updated_at": doc.get("dateModified", ""),
            })
        except (json.JSONDecodeError, OSError, KeyError) as exc:
            logger.warning("Failed to list demo context %s: %s", path.name, exc)
    return results


# ---------------------------------------------------------------------------
# Schema directory resolution
# ---------------------------------------------------------------------------

def _schemas_dir() -> Path:
    """Resolve the canonical schemas directory.

    Resolution order:

    1. ``SCHEMAS_DIR`` environment variable (useful for tests and deployment).
    2. ``schemas/`` at the repository root, resolved from this file's location:
       ``storage/schemas.py`` → ``.parent`` (package dir) →
       ``.parent`` (repo root) → ``schemas/``.
    """
    override = os.environ.get("SCHEMAS_DIR")
    if override:
        return Path(override)
    # storage/schemas.py → .parent = storage/ → .parent = repo root
    repo_root = Path(__file__).parent.parent
    return repo_root / "schemas"


# ---------------------------------------------------------------------------
# Schema definition accessors (read-only, disk-based)
# ---------------------------------------------------------------------------

def list_schemas() -> list[dict[str, Any]]:
    """Return metadata for all registered mind schemas.

    Each entry includes ``name``, ``filename``, ``available``, ``title``,
    and ``description`` (populated from the schema file when present).
    """
    schemas_dir = _schemas_dir()
    result: list[dict[str, Any]] = []
    for name, filename in SCHEMA_REGISTRY.items():
        path = schemas_dir / filename
        entry: dict[str, Any] = {
            "name": name,
            "filename": filename,
            "available": path.exists(),
            "title": "",
            "description": "",
        }
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            entry["title"] = data.get("title", "")
            entry["description"] = data.get("description", "")
        result.append(entry)
    return result


def get_schema(schema_name: str) -> dict[str, Any] | None:
    """Load and return a JSON Schema definition by name.

    Returns ``None`` if the name is not registered or the file is absent.
    """
    filename = SCHEMA_REGISTRY.get(schema_name)
    if filename is None:
        return None
    schema_path = _schemas_dir() / filename
    if not schema_path.exists():
        return None
    return json.loads(schema_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Azure Table Storage connection helpers
# ---------------------------------------------------------------------------

def _service_client() -> TableServiceClient:
    conn_str = _storage_conn_str()
    return TableServiceClient.from_connection_string(conn_str)


def _schema_contexts_client():
    svc = _service_client()
    try:
        svc.create_table(SCHEMA_CONTEXTS_TABLE)
    except Exception:  # noqa: BLE001 — table already exists
        pass
    return svc.get_table_client(SCHEMA_CONTEXTS_TABLE)


# ---------------------------------------------------------------------------
# Schema context CRUD (Azure Table Storage–backed, with demo-data fallback)
# ---------------------------------------------------------------------------

def store_schema_context(
    schema_name: str,
    context_id: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Persist a JSON-LD document that conforms to a mind schema.

    Args:
        schema_name: Name of the schema this context conforms to
            (e.g. ``"manas"``, ``"buddhi"``, ``"chitta"``).
        context_id: Unique identifier for this context — typically the
            agent id (e.g. ``"ceo"``) or a compound key for entity
            perspectives (e.g. ``"ceo/company"``).
        data: The JSON-LD document to persist.

    Returns:
        Confirmation record with ``schema_name``, ``context_id``, and
        ``updated_at``.
    """
    client = _schema_contexts_client()
    now_iso = datetime.now(UTC).isoformat()
    entity: dict[str, Any] = {
        "PartitionKey": schema_name,
        "RowKey": context_id,
        "Content": json.dumps(data, ensure_ascii=False),
        "UpdatedAt": now_iso,
    }
    client.upsert_entity(entity)
    logger.info("Stored schema context %s/%s", schema_name, context_id)
    return {"schema_name": schema_name, "context_id": context_id, "updated_at": now_iso}


def get_schema_context(
    schema_name: str,
    context_id: str,
) -> dict[str, Any] | None:
    """Retrieve a previously stored schema context document.

    Returns ``None`` if the context has not been stored yet.
    """
    if _use_demo_data():
        return _load_demo_schema_context(schema_name, context_id)
    client = _schema_contexts_client()
    try:
        entity = client.get_entity(partition_key=schema_name, row_key=context_id)
    except ResourceNotFoundError:
        return None
    content_raw = entity.get("Content", "{}")
    content = json.loads(content_raw) if isinstance(content_raw, str) else content_raw
    return {
        "schema_name": schema_name,
        "context_id": context_id,
        "data": content,
        "updated_at": entity.get("UpdatedAt", ""),
    }


def list_schema_contexts(
    schema_name: str | None = None,
) -> list[dict[str, Any]]:
    """List stored schema contexts, optionally filtered by schema name.

    Args:
        schema_name: When provided only contexts for this schema are returned.

    Returns:
        List of summary records containing ``schema_name``, ``context_id``,
        and ``updated_at``.
    """
    if _use_demo_data():
        return _list_demo_schema_contexts(schema_name)
    client = _schema_contexts_client()
    if schema_name:
        query = f"PartitionKey eq '{schema_name}'"
    else:
        query = "PartitionKey ne ''"
    entities = client.query_entities(query)
    return [
        {
            "schema_name": e.get("PartitionKey", ""),
            "context_id": e.get("RowKey", ""),
            "updated_at": e.get("UpdatedAt", ""),
        }
        for e in entities
    ]
