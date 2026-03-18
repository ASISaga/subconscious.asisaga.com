"""Tests for subconscious.models — Pydantic data models."""

from __future__ import annotations

from subconscious.models import ConversationPage, Message, MessageInput, Orchestration


class TestMessageInput:
    def test_basic_creation(self):
        m = MessageInput(agent_id="a", role="user", content="Hello")
        assert m.agent_id == "a"
        assert m.role == "user"
        assert m.content == "Hello"
        assert m.metadata is None

    def test_with_metadata(self):
        m = MessageInput(agent_id="b", role="tool", content="Result", metadata={"key": "val"})
        assert m.metadata == {"key": "val"}


class TestMessage:
    def test_full_message(self):
        m = Message(
            orchestration_id="orch-1",
            sequence="msg_001",
            created_at="2026-01-01T00:00:00Z",
            agent_id="a",
            role="assistant",
            content="Hello",
        )
        assert m.orchestration_id == "orch-1"
        assert m.sequence == "msg_001"


class TestOrchestration:
    def test_defaults(self):
        o = Orchestration(orchestration_id="orch-1")
        assert o.purpose == ""
        assert o.status == "active"
        assert o.agents == []
        assert o.message_count == 0
        assert o.created_at  # should be auto-generated
        assert o.updated_at

    def test_with_agents(self):
        o = Orchestration(orchestration_id="orch-2", purpose="Test", agents=["a", "b"])
        assert o.agents == ["a", "b"]


class TestConversationPage:
    def test_empty_page(self):
        page = ConversationPage(orchestration_id="orch-1", messages=[], total=0)
        assert page.has_more is False

    def test_with_messages(self):
        msg = Message(
            orchestration_id="orch-1",
            sequence="msg_001",
            created_at="2026-01-01T00:00:00Z",
            agent_id="a",
            role="user",
            content="Hello",
        )
        page = ConversationPage(orchestration_id="orch-1", messages=[msg], total=1, has_more=True)
        assert page.total == 1
        assert page.has_more is True
