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
_SKIP_MIND_DIRS = {"collective"}

#: Default company identifier used when no ``company_id`` is supplied.
#: Provision: when multiple companies/products are onboarded, callers pass an
#: explicit ``company_id`` to scope storage rows independently.
DEFAULT_COMPANY_ID: str | None = None


def _scoped_row_key(company_id: str | None, context_id: str) -> str:
    """Return a RowKey scoped by *company_id* when one is provided.

    When *company_id* is ``None`` the plain *context_id* is returned unchanged,
    preserving backward compatibility with rows written before multi-company
    support was introduced.  When a *company_id* is supplied the key takes the
    form ``{company_id}/{context_id}`` so that data for different companies
    occupies distinct rows in the same Azure Table partition.

    Args:
        company_id: Optional company scope (e.g. ``"asisaga"``).
        context_id: The existing context identifier (e.g. ``"ceo"``).

    Returns:
        Scoped row key string.
    """
    if company_id:
        return f"{company_id}/{context_id}"
    return context_id

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


def _mind_dir() -> Path:
    """Resolve the canonical mind directory used for storage initialization."""
    override = os.environ.get("MIND_DIR")
    if override:
        return Path(override)
    return Path(__file__).parent.parent / "mind"


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


def _schema_contexts_empty(client: Any) -> bool:
    """Return ``True`` when the SchemaContexts table has no rows."""
    entities = client.query_entities("PartitionKey ne ''")
    return next(iter(entities), None) is None


def _load_json_file(path: Path) -> dict[str, Any] | None:
    """Load a JSON/JSON-LD file and return its dict payload."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed loading mind seed file %s: %s", path, exc)
        return None
    if not isinstance(payload, dict):
        logger.warning("Skipping non-object mind seed file %s", path)
        return None
    return payload


def _first_existing_path(candidates: list[Path]) -> Path | None:
    """Return first existing path from *candidates*, else ``None``."""
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _collect_mind_seed_records(mind_dir: Path) -> list[dict[str, Any]]:
    """Collect bootstrap schema-context records from the mind directory."""
    records: list[dict[str, Any]] = []
    if not mind_dir.is_dir():
        return records
    for agent_dir in sorted(p for p in mind_dir.iterdir() if p.is_dir()):
        agent_id = agent_dir.name
        if agent_id in _SKIP_MIND_DIRS:
            # Collective files represent shared boardroom state, not per-agent
            # schema contexts keyed by a single agent identifier.
            continue

        direct_files: list[tuple[str, Path | None]] = [
            (
                "manas",
                _first_existing_path([
                    agent_dir / "manas" / f"{agent_id}.jsonld",
                    agent_dir / "Manas" / f"{agent_id}.jsonld",
                ]),
            ),
            (
                "buddhi",
                _first_existing_path([
                    agent_dir / "buddhi" / "buddhi.jsonld",
                    agent_dir / "Buddhi" / "buddhi.jsonld",
                ]),
            ),
            (
                "action-plan",
                _first_existing_path([
                    agent_dir / "buddhi" / "action-plan.jsonld",
                    agent_dir / "Buddhi" / "action-plan.jsonld",
                ]),
            ),
            (
                "ahankara",
                _first_existing_path([
                    agent_dir / "ahankara" / "ahankara.jsonld",
                    agent_dir / "Ahankara" / "ahankara.jsonld",
                ]),
            ),
            (
                "chitta",
                _first_existing_path([
                    agent_dir / "chitta" / "chitta.jsonld",
                    agent_dir / "Chitta" / "chitta.jsonld",
                ]),
            ),
            (
                "integrity",
                _first_existing_path([
                    agent_dir / "integrity" / "integrity.jsonld",
                    agent_dir / "Integrity" / "integrity.jsonld",
                ]),
            ),
        ]
        for schema_name, path in direct_files:
            if path is None:
                continue
            payload = _load_json_file(path)
            if payload is None:
                continue
            records.append({
                "schema_name": schema_name,
                "context_id": agent_id,
                "data": payload,
            })

        responsibilities_dir = _first_existing_path(
            [agent_dir / "responsibilities", agent_dir / "Responsibilities"]
        )
        if responsibilities_dir and responsibilities_dir.is_dir():
            for path in sorted(responsibilities_dir.glob("*.jsonld")):
                payload = _load_json_file(path)
                if payload is None:
                    continue
                context_key = f"{agent_id}/{path.stem}"
                records.append({
                    "schema_name": "responsibilities",
                    "context_id": context_key,
                    "data": payload,
                })

        for schema_name, relative in (
            ("entity-context", ("manas", "context")),
            ("entity-content", ("manas", "content")),
        ):
            folder = _first_existing_path([
                agent_dir.joinpath(*relative),
                agent_dir.joinpath(*[part.capitalize() for part in relative]),
            ])
            if folder is None or not folder.is_dir():
                continue
            for path in sorted(folder.glob("*.jsonld")):
                payload = _load_json_file(path)
                if payload is None:
                    continue
                context_key = f"{agent_id}/{path.stem}"
                records.append({
                    "schema_name": schema_name,
                    "context_id": context_key,
                    "data": payload,
                })
    return records


# ---------------------------------------------------------------------------
# Schema context CRUD (Azure Table Storage–backed, with demo-data fallback)
# ---------------------------------------------------------------------------

def store_schema_context(
    schema_name: str,
    context_id: str,
    data: dict[str, Any],
    company_id: str | None = None,
) -> dict[str, Any]:
    """Persist a JSON-LD document that conforms to a mind schema.

    Args:
        schema_name: Name of the schema this context conforms to
            (e.g. ``"manas"``, ``"buddhi"``, ``"chitta"``).
        context_id: Unique identifier for this context — typically the
            agent id (e.g. ``"ceo"``) or a compound key for entity
            perspectives (e.g. ``"ceo/company"``).
        data: The JSON-LD document to persist.
        company_id: Optional company scope (e.g. ``"asisaga"``).  When
            supplied the RowKey is prefixed with ``{company_id}/`` so
            that data for different companies occupies distinct rows.
            Provision for multi-company/product scaling.

    Returns:
        Confirmation record with ``schema_name``, ``context_id``, and
        ``updated_at``.
    """
    client = _schema_contexts_client()
    now_iso = datetime.now(UTC).isoformat()
    row_key = _scoped_row_key(company_id, context_id)
    entity: dict[str, Any] = {
        "PartitionKey": schema_name,
        "RowKey": row_key,
        "Content": json.dumps(data, ensure_ascii=False),
        "UpdatedAt": now_iso,
    }
    if company_id:
        entity["CompanyId"] = company_id
    client.upsert_entity(entity)
    logger.info("Stored schema context %s/%s (company=%s)", schema_name, context_id, company_id)
    return {"schema_name": schema_name, "context_id": context_id, "updated_at": now_iso}


def get_schema_context(
    schema_name: str,
    context_id: str,
    company_id: str | None = None,
) -> dict[str, Any] | None:
    """Retrieve a previously stored schema context document.

    Args:
        schema_name: The schema the context conforms to (e.g. ``"manas"``).
        context_id: The context identifier (e.g. ``"ceo"``).
        company_id: Optional company scope.  Must match the value used
            when the context was stored.  Provision for multi-company scaling.

    Returns ``None`` if the context has not been stored yet.
    """
    if _use_demo_data():
        return _load_demo_schema_context(schema_name, context_id)
    client = _schema_contexts_client()
    row_key = _scoped_row_key(company_id, context_id)
    try:
        entity = client.get_entity(partition_key=schema_name, row_key=row_key)
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
    company_id: str | None = None,
) -> list[dict[str, Any]]:
    """List stored schema contexts, optionally filtered by schema name and company.

    Args:
        schema_name: When provided only contexts for this schema are returned.
        company_id: Optional company scope.  When provided only contexts stored
            under this company are returned.  Provision for multi-company scaling.

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
    if company_id:
        query += f" and CompanyId eq '{company_id}'"
    entities = client.query_entities(query)
    results = []
    for e in entities:
        row_key: str = e.get("RowKey", "")
        stored_company = e.get("CompanyId", "")
        # Strip company prefix from RowKey so callers see the plain context_id
        if stored_company and row_key.startswith(f"{stored_company}/"):
            ctx_id = row_key[len(stored_company) + 1:]
        else:
            ctx_id = row_key
        results.append({
            "schema_name": e.get("PartitionKey", ""),
            "context_id": ctx_id,
            "updated_at": e.get("UpdatedAt", ""),
        })
    return results


def initialize_schema_contexts_from_mind(
    force: bool = False,
    company_id: str | None = None,
) -> dict[str, Any]:
    """Initialize SchemaContexts rows from the repository ``mind`` directory.

    Initialization is intended as a one-time bootstrap. By default, the process
    is skipped when the table already contains records. Set ``force=True`` to
    overwrite existing rows with the latest file payloads.

    Args:
        force: When ``True``, writes mind data even when the table already
            contains records.
        company_id: Optional company scope.  When provided every seeded row is
            stored under ``{company_id}/{context_id}`` and annotated with a
            ``CompanyId`` attribute.  Provision for multi-company scaling.
    """
    if _use_demo_data():
        return {
            "initialized": False,
            "reason": "demo-mode",
            "seeded": 0,
            "mind_dir": str(_mind_dir()),
        }

    client = _schema_contexts_client()
    if not force and not _schema_contexts_empty(client):
        return {
            "initialized": False,
            "reason": "table-not-empty",
            "seeded": 0,
            "mind_dir": str(_mind_dir()),
        }

    mind_dir = _mind_dir()
    records = _collect_mind_seed_records(mind_dir)
    now_iso = datetime.now(UTC).isoformat()
    for record in records:
        row_key = _scoped_row_key(company_id, record["context_id"])
        entity: dict[str, Any] = {
            "PartitionKey": record["schema_name"],
            "RowKey": row_key,
            "Content": json.dumps(record["data"], ensure_ascii=False),
            "UpdatedAt": now_iso,
        }
        if company_id:
            entity["CompanyId"] = company_id
        client.upsert_entity(entity)

    logger.info("Initialized schema contexts from mind directory: %d rows", len(records))
    return {
        "initialized": True,
        "reason": "ok",
        "seeded": len(records),
        "mind_dir": str(mind_dir),
        "force": force,
    }
