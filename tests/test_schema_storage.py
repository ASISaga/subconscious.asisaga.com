"""Tests for subconscious.schema_storage — schema definition serving and context persistence."""

from __future__ import annotations

import json

import pytest

from subconscious import schema_storage


class TestSchemaRegistry:
    """Verify the schema registry covers all 7 mind dimensions."""

    def test_all_expected_schemas_registered(self):
        expected = {
            "manas", "buddhi", "ahankara", "chitta",
            "action-plan", "entity-context", "entity-content",
        }
        assert expected == set(schema_storage.SCHEMA_REGISTRY.keys())

    def test_filenames_are_json_schema(self):
        for filename in schema_storage.SCHEMA_REGISTRY.values():
            assert filename.endswith(".schema.json"), f"{filename} should end with .schema.json"


class TestListSchemas:
    """list_schemas() using the fixture-provided tmp schemas dir."""

    def test_list_returns_all_registered(self, schemas_dir):
        result = schema_storage.list_schemas()
        assert len(result) == 7

    def test_all_available_when_files_present(self, schemas_dir):
        result = schema_storage.list_schemas()
        for entry in result:
            assert entry["available"] is True, f"{entry['name']} should be available"

    def test_entries_have_title_and_description(self, schemas_dir):
        result = schema_storage.list_schemas()
        for entry in result:
            assert entry["title"], f"{entry['name']} should have a title"
            assert entry["description"], f"{entry['name']} should have a description"

    def test_unavailable_when_no_files(self, monkeypatch, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        monkeypatch.setenv("SCHEMAS_DIR", str(empty_dir))
        result = schema_storage.list_schemas()
        for entry in result:
            assert entry["available"] is False
            assert entry["title"] == ""


class TestGetSchema:
    """get_schema() returns the schema dict or None."""

    def test_get_known_schema(self, schemas_dir):
        result = schema_storage.get_schema("manas")
        assert result is not None
        assert result["title"] == "Manas — Agent Memory State"

    def test_get_all_schemas(self, schemas_dir):
        for name in schema_storage.SCHEMA_REGISTRY:
            result = schema_storage.get_schema(name)
            assert result is not None, f"get_schema('{name}') should not be None"

    def test_get_unknown_schema_returns_none(self, schemas_dir):
        result = schema_storage.get_schema("nonexistent")
        assert result is None

    def test_get_schema_without_files_returns_none(self, monkeypatch, tmp_path):
        empty = tmp_path / "e"
        empty.mkdir()
        monkeypatch.setenv("SCHEMAS_DIR", str(empty))
        result = schema_storage.get_schema("manas")
        assert result is None


class TestSchemaContextCRUD:
    """store_schema_context / get_schema_context / list_schema_contexts."""

    def test_store_and_retrieve_context(self, schemas_dir):
        doc = {"@context": "https://asisaga.com/contexts/buddhi.jsonld", "@type": "Buddhi", "agent_id": "ceo"}
        result = schema_storage.store_schema_context("buddhi", "ceo", doc)
        assert result["schema_name"] == "buddhi"
        assert result["context_id"] == "ceo"
        assert "updated_at" in result

        retrieved = schema_storage.get_schema_context("buddhi", "ceo")
        assert retrieved is not None
        assert retrieved["data"] == doc
        assert retrieved["schema_name"] == "buddhi"
        assert retrieved["context_id"] == "ceo"

    def test_get_context_not_found_returns_none(self):
        result = schema_storage.get_schema_context("manas", "ghost")
        assert result is None

    def test_overwrite_context(self, schemas_dir):
        doc1 = {"version": 1}
        doc2 = {"version": 2}
        schema_storage.store_schema_context("chitta", "cfo", doc1)
        schema_storage.store_schema_context("chitta", "cfo", doc2)
        retrieved = schema_storage.get_schema_context("chitta", "cfo")
        assert retrieved["data"]["version"] == 2

    def test_list_contexts_filtered_by_schema(self, schemas_dir):
        schema_storage.store_schema_context("manas", "ceo", {"a": 1})
        schema_storage.store_schema_context("manas", "cfo", {"b": 2})
        schema_storage.store_schema_context("buddhi", "ceo", {"c": 3})

        manas_list = schema_storage.list_schema_contexts("manas")
        assert len(manas_list) == 2
        ids = {r["context_id"] for r in manas_list}
        assert ids == {"ceo", "cfo"}

    def test_list_all_contexts(self, schemas_dir):
        schema_storage.store_schema_context("manas", "ceo", {})
        schema_storage.store_schema_context("buddhi", "cfo", {})
        schema_storage.store_schema_context("chitta", "coo", {})

        all_contexts = schema_storage.list_schema_contexts()
        assert len(all_contexts) == 3

    def test_list_contexts_empty(self):
        result = schema_storage.list_schema_contexts("manas")
        assert result == []

    def test_compound_context_id(self, schemas_dir):
        """Entity perspective contexts use compound keys like 'ceo/company'."""
        doc = {"@type": "SagaEntity", "agent_perspective": "agent:ceo"}
        schema_storage.store_schema_context("entity-context", "ceo/company", doc)
        retrieved = schema_storage.get_schema_context("entity-context", "ceo/company")
        assert retrieved is not None
        assert retrieved["data"] == doc

    def test_unicode_content_round_trip(self, schemas_dir):
        """Unicode characters in JSON-LD values should survive storage."""
        doc = {"label": "純粋知性 (Pure Intelligence)", "emoji": "🧠"}
        schema_storage.store_schema_context("chitta", "ceo", doc)
        retrieved = schema_storage.get_schema_context("chitta", "ceo")
        assert retrieved["data"]["label"] == "純粋知性 (Pure Intelligence)"
