"""Tests for subconscious.app — pure-Python handler functions (no Starlette)."""

from __future__ import annotations

import pytest

from subconscious import schema_storage, storage
from subconscious import app as handlers


class TestHealthHandler:
    def test_health_returns_healthy(self):
        result = handlers.get_health()
        assert result["status"] == "healthy"
        assert result["service"] == "subconscious"

    def test_health_has_jsonld_context(self):
        result = handlers.get_health()
        assert result["@context"] == "https://schema.org/"
        assert result["@type"] == "HealthAspect"


class TestOrchestrationsHandlers:
    def test_list_empty(self):
        result = handlers.list_orchestrations()
        assert result == []

    def test_list_with_data(self):
        storage.create_orchestration("h-1", "Purpose A")
        storage.create_orchestration("h-2", "Purpose B")
        result = handlers.list_orchestrations()
        assert len(result) == 2

    def test_list_has_jsonld_annotations(self):
        storage.create_orchestration("h-3", "Test")
        result = handlers.list_orchestrations()
        assert len(result) == 1
        item = result[0]
        assert item["@context"] == "https://schema.org/"
        assert item["@type"] == "Action"
        assert "actionStatus" in item
        assert item["orchestration_id"] == "h-3"

    def test_list_filter_by_status(self):
        storage.create_orchestration("h-4", "Active one")
        storage.create_orchestration("h-5", "Completed one")
        storage.update_orchestration_status("h-5", "completed")
        result = handlers.list_orchestrations(status="completed")
        assert len(result) == 1
        assert result[0]["orchestration_id"] == "h-5"

    def test_get_orchestration_found(self):
        storage.create_orchestration("h-6", "Detail test")
        result = handlers.get_orchestration("h-6")
        assert result is not None
        assert result["orchestration_id"] == "h-6"
        assert result["@type"] == "Action"

    def test_get_orchestration_not_found(self):
        result = handlers.get_orchestration("nonexistent")
        assert result is None

    def test_action_status_mapping_active(self):
        storage.create_orchestration("h-7", "Active")
        result = handlers.get_orchestration("h-7")
        assert result["actionStatus"] == "https://schema.org/ActiveActionStatus"

    def test_action_status_mapping_completed(self):
        storage.create_orchestration("h-8", "Completed")
        storage.update_orchestration_status("h-8", "completed")
        result = handlers.get_orchestration("h-8")
        assert result["actionStatus"] == "https://schema.org/CompletedActionStatus"


class TestConversationHandlers:
    def test_get_conversation_empty(self):
        result = handlers.get_conversation("empty-orch")
        assert result["orchestration_id"] == "empty-orch"
        assert result["messages"] == []
        assert result["total"] == 0
        assert result["@type"] == "Conversation"

    def test_get_conversation_with_messages(self):
        storage.create_orchestration("c-1", "Conv test")
        storage.persist_message("c-1", "agent-a", "user", "Hello")
        storage.persist_message("c-1", "agent-b", "assistant", "Hi there")
        result = handlers.get_conversation("c-1")
        assert result["total"] == 2
        assert len(result["messages"]) == 2

    def test_messages_have_jsonld_annotations(self):
        storage.create_orchestration("c-2", "JSON-LD test")
        storage.persist_message("c-2", "agent-x", "user", "Test message")
        result = handlers.get_conversation("c-2")
        msg = result["messages"][0]
        assert msg["@type"] == "Message"
        assert msg["agent_id"] == "agent-x"
        assert msg["content"] == "Test message"
        assert "sender" in msg
        assert msg["sender"]["identifier"] == "agent-x"
        assert msg["text"] == "Test message"

    def test_get_conversation_with_limit(self):
        storage.create_orchestration("c-3", "Limit test")
        for i in range(5):
            storage.persist_message("c-3", "a", "user", f"msg-{i}")
        result = handlers.get_conversation("c-3", limit=2)
        assert result["total"] == 2


class TestSchemasHandlers:
    def test_list_schemas(self, schemas_dir):
        result = handlers.list_schemas()
        assert len(result) == 7
        names = {s["name"] for s in result}
        assert "manas" in names
        assert "buddhi" in names
        assert "chitta" in names

    def test_get_schema_known(self, schemas_dir):
        result = handlers.get_schema("manas")
        assert result is not None
        assert result["title"] == "Manas — Agent Memory State"

    def test_get_schema_not_found(self, schemas_dir):
        result = handlers.get_schema("unknown")
        assert result is None

    def test_get_schema_available(self):
        available = handlers.get_schema_available()
        assert "manas" in available
        assert "buddhi" in available
        assert len(available) == 7


class TestSchemaContextsHandlers:
    def test_list_schema_contexts_empty(self):
        result = handlers.list_schema_contexts()
        assert result == []

    def test_store_and_get_schema_context(self, schemas_dir):
        doc = {"@type": "Buddhi", "agent_id": "ceo", "name": "Steve Jobs"}
        put_result = handlers.store_schema_context("buddhi", "ceo", doc)
        assert put_result["schema_name"] == "buddhi"
        assert put_result["context_id"] == "ceo"

        get_result = handlers.get_schema_context("buddhi", "ceo")
        assert get_result is not None
        assert get_result["data"] == doc

    def test_get_schema_context_not_found(self):
        result = handlers.get_schema_context("manas", "ghost")
        assert result is None

    def test_list_schema_contexts_after_store(self, schemas_dir):
        schema_storage.store_schema_context("manas", "ceo", {})
        schema_storage.store_schema_context("manas", "cfo", {})
        result = handlers.list_schema_contexts("manas")
        assert len(result) == 2


class TestAppHtml:
    def test_app_html_exists(self):
        html = handlers.get_app_html()
        assert isinstance(html, str)
        assert len(html) > 0

    def test_app_html_contains_ui_elements(self):
        html = handlers.get_app_html()
        assert "Subconscious" in html
        assert "orch-list" in html
        assert "/mcp" in html
        assert "<!DOCTYPE html>" in html
