"""Shared test fixtures for the subconscious test suite."""

from __future__ import annotations

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
