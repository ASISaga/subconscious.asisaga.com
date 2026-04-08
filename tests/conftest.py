"""Shared test fixtures for the subconscious test suite."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Fake Azure Table Storage
# ---------------------------------------------------------------------------

class FakeTableClient:
    """In-memory replacement for ``azure.data.tables.TableClient``."""

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], dict[str, Any]] = {}

    def upsert_entity(self, entity: dict[str, Any]) -> None:
        pk = entity["PartitionKey"]
        rk = entity["RowKey"]
        self._store[(pk, rk)] = dict(entity)

    def get_entity(self, *, partition_key: str, row_key: str) -> dict[str, Any]:
        key = (partition_key, row_key)
        if key not in self._store:
            from azure.core.exceptions import ResourceNotFoundError

            raise ResourceNotFoundError("Entity not found")
        return dict(self._store[key])

    def query_entities(self, query: str) -> list[dict[str, Any]]:
        """Very basic query support — filters on PartitionKey and optional Status."""
        results: list[dict[str, Any]] = []
        parts = query.split(" and ")
        filters: dict[str, str] = {}
        for part in parts:
            part = part.strip()
            if " eq " in part:
                field, val = part.split(" eq ", 1)
                filters[field.strip()] = val.strip().strip("'")
            elif " ne " in part:
                # Support PartitionKey ne '' (used by list_schema_contexts)
                pass
        for (pk, _rk), entity in self._store.items():
            match = True
            if "PartitionKey" in filters and pk != filters["PartitionKey"]:
                match = False
            if "Status" in filters and entity.get("Status") != filters["Status"]:
                match = False
            if match:
                results.append(dict(entity))
        return results


class FakeTableServiceClient:
    """In-memory replacement for ``azure.data.tables.TableServiceClient``."""

    _tables: dict[str, FakeTableClient] = {}

    def __init__(self) -> None:
        pass

    @classmethod
    def from_connection_string(cls, _conn_str: str) -> FakeTableServiceClient:
        return cls()

    def create_table(self, name: str) -> None:
        if name not in FakeTableServiceClient._tables:
            FakeTableServiceClient._tables[name] = FakeTableClient()

    def get_table_client(self, name: str) -> FakeTableClient:
        if name not in FakeTableServiceClient._tables:
            FakeTableServiceClient._tables[name] = FakeTableClient()
        return FakeTableServiceClient._tables[name]


@pytest.fixture(autouse=True)
def _fake_storage(monkeypatch):
    """Replace Azure Table Storage with in-memory fakes for every test."""
    FakeTableServiceClient._tables = {}
    monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "DefaultEndpointsProtocol=https;AccountName=fake")
    monkeypatch.setattr(
        "subconscious.storage.TableServiceClient",
        FakeTableServiceClient,
    )
    monkeypatch.setattr(
        "subconscious.schema_storage.TableServiceClient",
        FakeTableServiceClient,
    )


@pytest.fixture()
def schemas_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Provide a temporary schemas directory pre-populated with minimal schema files."""
    schemas = tmp_path / "schemas"
    schemas.mkdir()

    # Write minimal JSON Schema stubs for all 7 registered names
    schema_stubs = {
        "manas.schema.json": {
            "$id": "https://asisaga.com/schemas/mind/manas.schema.json",
            "title": "Manas — Agent Memory State",
            "description": "Agent memory state schema.",
            "type": "object",
        },
        "buddhi.schema.json": {
            "$id": "https://asisaga.com/schemas/mind/buddhi.schema.json",
            "title": "Buddhi — Agent Intellect",
            "description": "Agent intellect schema.",
            "type": "object",
        },
        "ahankara.schema.json": {
            "$id": "https://asisaga.com/schemas/mind/ahankara.schema.json",
            "title": "Ahankara — Agent Identity",
            "description": "Agent identity schema.",
            "type": "object",
        },
        "chitta.schema.json": {
            "$id": "https://asisaga.com/schemas/mind/chitta.schema.json",
            "title": "Chitta — Pure Intelligence",
            "description": "Pure intelligence schema.",
            "type": "object",
        },
        "action-plan.schema.json": {
            "$id": "https://asisaga.com/schemas/mind/action-plan.schema.json",
            "title": "AgentActionPlan — Buddhi Action Plan",
            "description": "Action plan schema.",
            "type": "object",
        },
        "entity-context.schema.json": {
            "$id": "https://asisaga.com/schemas/mind/entity-context.schema.json",
            "title": "Entity Context Perspective — Immutable",
            "description": "Entity context schema.",
            "type": "object",
        },
        "entity-content.schema.json": {
            "$id": "https://asisaga.com/schemas/mind/entity-content.schema.json",
            "title": "Entity Content Perspective — Mutable",
            "description": "Entity content schema.",
            "type": "object",
        },
    }
    import json

    for filename, content in schema_stubs.items():
        (schemas / filename).write_text(json.dumps(content), encoding="utf-8")

    monkeypatch.setenv("SCHEMAS_DIR", str(schemas))
    return schemas
