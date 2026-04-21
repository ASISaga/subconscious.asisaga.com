"""Tests for storage.schemas — schema definition serving and context persistence."""

from __future__ import annotations

import json

from storage import schemas as schema_storage


class TestSchemaRegistry:
    """Verify the schema registry covers all 7 mind dimensions."""

    def test_all_expected_schemas_registered(self):
        expected = {
            "manas", "buddhi", "ahankara", "chitta",
            "action-plan", "entity-context", "entity-content",
            "responsibilities", "integrity",
        }
        assert expected == set(schema_storage.SCHEMA_REGISTRY.keys())

    def test_filenames_are_json_schema(self):
        for filename in schema_storage.SCHEMA_REGISTRY.values():
            assert filename.endswith(".schema.json"), f"{filename} should end with .schema.json"


class TestListSchemas:
    """list_schemas() using the fixture-provided tmp schemas dir."""

    def test_list_returns_all_registered(self, schemas_dir):
        result = schema_storage.list_schemas()
        assert len(result) == 9

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


class TestCompanyIdScoping:
    """company_id provision — multi-company/product scoping in Azure Tables."""

    def test_store_and_retrieve_with_company_id(self, schemas_dir):
        """Rows stored with company_id are retrievable with the same company_id."""
        doc = {"@type": "Manas", "agent_id": "ceo"}
        schema_storage.store_schema_context("manas", "ceo", doc, company_id="asisaga")
        result = schema_storage.get_schema_context("manas", "ceo", company_id="asisaga")
        assert result is not None
        assert result["data"] == doc
        assert result["context_id"] == "ceo"

    def test_company_scoped_row_not_found_without_scope(self, schemas_dir):
        """A row stored with company_id is not returned when no company_id is given."""
        doc = {"@type": "Manas"}
        schema_storage.store_schema_context("manas", "ceo", doc, company_id="asisaga")
        # Without company scope the plain RowKey 'ceo' does not exist
        result = schema_storage.get_schema_context("manas", "ceo")
        assert result is None

    def test_unscoped_row_not_found_with_company_id(self, schemas_dir):
        """A row stored without company_id is not returned when company_id is given."""
        doc = {"@type": "Manas"}
        schema_storage.store_schema_context("manas", "ceo", doc)
        result = schema_storage.get_schema_context("manas", "ceo", company_id="asisaga")
        assert result is None

    def test_different_companies_isolated(self, schemas_dir):
        """Rows for different companies are independently addressable."""
        doc_a = {"company": "asisaga"}
        doc_b = {"company": "techcorp"}
        schema_storage.store_schema_context("buddhi", "ceo", doc_a, company_id="asisaga")
        schema_storage.store_schema_context("buddhi", "ceo", doc_b, company_id="techcorp")

        result_a = schema_storage.get_schema_context("buddhi", "ceo", company_id="asisaga")
        result_b = schema_storage.get_schema_context("buddhi", "ceo", company_id="techcorp")
        assert result_a["data"] == doc_a
        assert result_b["data"] == doc_b

    def test_list_contexts_filtered_by_company_id(self, schemas_dir):
        """list_schema_contexts with company_id returns only that company's rows."""
        schema_storage.store_schema_context("chitta", "ceo", {}, company_id="asisaga")
        schema_storage.store_schema_context("chitta", "cfo", {}, company_id="asisaga")
        schema_storage.store_schema_context("chitta", "ceo", {}, company_id="techcorp")

        asisaga_list = schema_storage.list_schema_contexts("chitta", company_id="asisaga")
        assert len(asisaga_list) == 2
        ids = {r["context_id"] for r in asisaga_list}
        assert ids == {"ceo", "cfo"}

        techcorp_list = schema_storage.list_schema_contexts("chitta", company_id="techcorp")
        assert len(techcorp_list) == 1
        assert techcorp_list[0]["context_id"] == "ceo"

    def test_list_context_ids_stripped_of_company_prefix(self, schemas_dir):
        """context_id in list results has the company prefix stripped."""
        schema_storage.store_schema_context("manas", "cfo", {}, company_id="asisaga")
        results = schema_storage.list_schema_contexts("manas", company_id="asisaga")
        assert results[0]["context_id"] == "cfo"

    def test_initialize_with_company_id(self, tmp_path, monkeypatch):
        """initialize_schema_contexts_from_mind respects company_id scoping."""
        mind_dir = tmp_path / "mind"
        (mind_dir / "ceo" / "manas").mkdir(parents=True)
        (mind_dir / "ceo" / "manas" / "ceo.jsonld").write_text(
            json.dumps({"@type": "Manas"}), encoding="utf-8"
        )
        monkeypatch.setenv("MIND_DIR", str(mind_dir))

        result = schema_storage.initialize_schema_contexts_from_mind(company_id="asisaga")
        assert result["initialized"] is True
        assert result["seeded"] == 1

        # Row is only accessible with the company scope
        assert schema_storage.get_schema_context("manas", "ceo", company_id="asisaga") is not None
        assert schema_storage.get_schema_context("manas", "ceo") is None


class TestInitializeSchemaContextsFromMind:
    """initialize_schema_contexts_from_mind() bootstrap behavior."""

    def test_initializes_from_mind_directory(self, tmp_path, monkeypatch):
        mind_dir = tmp_path / "mind"
        (mind_dir / "ceo" / "manas" / "context").mkdir(parents=True)
        (mind_dir / "ceo" / "manas" / "content").mkdir(parents=True)
        (mind_dir / "ceo" / "buddhi").mkdir(parents=True)
        (mind_dir / "ceo" / "ahankara").mkdir(parents=True)
        (mind_dir / "ceo" / "chitta").mkdir(parents=True)
        (mind_dir / "ceo" / "responsibilities").mkdir(parents=True)
        (mind_dir / "ceo" / "integrity").mkdir(parents=True)

        (mind_dir / "ceo" / "manas" / "ceo.jsonld").write_text(
            json.dumps({"@type": "Manas", "identifier": "ceo"}),
            encoding="utf-8",
        )
        (mind_dir / "ceo" / "buddhi" / "buddhi.jsonld").write_text(
            json.dumps({"@type": "Buddhi"}),
            encoding="utf-8",
        )
        (mind_dir / "ceo" / "buddhi" / "action-plan.jsonld").write_text(
            json.dumps({"@type": "AgentActionPlan"}),
            encoding="utf-8",
        )
        (mind_dir / "ceo" / "ahankara" / "ahankara.jsonld").write_text(
            json.dumps({"@type": "Ahankara"}),
            encoding="utf-8",
        )
        (mind_dir / "ceo" / "chitta" / "chitta.jsonld").write_text(
            json.dumps({"@type": "Chitta"}),
            encoding="utf-8",
        )
        (mind_dir / "ceo" / "responsibilities" / "manager.jsonld").write_text(
            json.dumps({"@type": "RoleResponsibilities"}),
            encoding="utf-8",
        )
        (mind_dir / "ceo" / "integrity" / "integrity.jsonld").write_text(
            json.dumps({"@type": "IntegrityRegister"}),
            encoding="utf-8",
        )
        (mind_dir / "ceo" / "manas" / "context" / "company.jsonld").write_text(
            json.dumps({"@type": "SagaEntity"}),
            encoding="utf-8",
        )
        (mind_dir / "ceo" / "manas" / "content" / "company.jsonld").write_text(
            json.dumps({"@type": "SagaEntity"}),
            encoding="utf-8",
        )

        monkeypatch.setenv("MIND_DIR", str(mind_dir))

        result = schema_storage.initialize_schema_contexts_from_mind()
        assert result["initialized"] is True
        assert result["seeded"] == 9

        assert schema_storage.get_schema_context("manas", "ceo") is not None
        assert schema_storage.get_schema_context("buddhi", "ceo") is not None
        assert schema_storage.get_schema_context("action-plan", "ceo") is not None
        assert schema_storage.get_schema_context("ahankara", "ceo") is not None
        assert schema_storage.get_schema_context("chitta", "ceo") is not None
        assert schema_storage.get_schema_context("integrity", "ceo") is not None
        assert (
            schema_storage.get_schema_context("responsibilities", "ceo/manager")
            is not None
        )
        assert (
            schema_storage.get_schema_context("entity-context", "ceo/company")
            is not None
        )
        assert (
            schema_storage.get_schema_context("entity-content", "ceo/company")
            is not None
        )

    def test_skips_when_table_already_has_data(self, tmp_path, monkeypatch):
        mind_dir = tmp_path / "mind"
        mind_dir.mkdir()
        monkeypatch.setenv("MIND_DIR", str(mind_dir))

        schema_storage.store_schema_context("manas", "seed", {"x": 1})
        result = schema_storage.initialize_schema_contexts_from_mind()
        assert result["initialized"] is False
        assert result["reason"] == "table-not-empty"
