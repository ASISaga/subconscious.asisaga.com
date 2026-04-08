"""Tests for subconscious.models — Pydantic model validation."""

from __future__ import annotations

from datetime import UTC, datetime

from subconscious.models import (
    ConversationPage,
    Message,
    MessageInput,
    Orchestration,
    SchemaContextRecord,
    SchemaEntry,
)


class TestMessageInput:
    def test_required_fields(self):
        msg = MessageInput(agent_id="ceo", role="assistant", content="Hello")
        assert msg.agent_id == "ceo"
        assert msg.role == "assistant"
        assert msg.content == "Hello"
        assert msg.metadata is None

    def test_with_metadata(self):
        msg = MessageInput(agent_id="ceo", role="tool", content="result", metadata={"k": "v"})
        assert msg.metadata == {"k": "v"}


class TestMessage:
    def test_full_message(self):
        msg = Message(
            agent_id="ceo",
            role="user",
            content="decision",
            orchestration_id="orch-1",
            sequence="msg_001",
            created_at="2024-01-01T00:00:00+00:00",
        )
        assert msg.orchestration_id == "orch-1"
        assert msg.sequence == "msg_001"


class TestOrchestration:
    def test_defaults(self):
        orch = Orchestration(orchestration_id="o1")
        assert orch.status == "active"
        assert orch.agents == []
        assert orch.message_count == 0

    def test_with_agents(self):
        orch = Orchestration(orchestration_id="o2", purpose="Test", agents=["ceo", "cfo"])
        assert len(orch.agents) == 2


class TestConversationPage:
    def test_empty_page(self):
        page = ConversationPage(orchestration_id="o1", messages=[], total=0)
        assert page.total == 0
        assert page.has_more is False


class TestSchemaEntry:
    def test_defaults(self):
        entry = SchemaEntry(name="manas", filename="manas.schema.json", available=True)
        assert entry.title == ""
        assert entry.description == ""

    def test_with_metadata(self):
        entry = SchemaEntry(
            name="buddhi",
            filename="buddhi.schema.json",
            available=True,
            title="Buddhi — Agent Intellect",
            description="Schema for intellect layer.",
        )
        assert entry.title == "Buddhi — Agent Intellect"


class TestSchemaContextRecord:
    def test_required_fields(self):
        record = SchemaContextRecord(schema_name="manas", context_id="ceo")
        assert record.schema_name == "manas"
        assert record.context_id == "ceo"
        assert record.updated_at  # auto-set

    def test_explicit_updated_at(self):
        ts = "2024-06-01T12:00:00+00:00"
        record = SchemaContextRecord(schema_name="chitta", context_id="cfo", updated_at=ts)
        assert record.updated_at == ts
