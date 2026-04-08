"""Tests for subconscious.storage — conversation persistence layer."""

from __future__ import annotations

import time

from subconscious import storage


class TestOrchestrationCRUD:
    """create / get / list / update orchestrations."""

    def test_create_orchestration(self):
        result = storage.create_orchestration("orch-1", "Test purpose", ["agent-a", "agent-b"])
        assert result["orchestration_id"] == "orch-1"
        assert result["purpose"] == "Test purpose"
        assert result["status"] == "active"
        assert result["agents"] == ["agent-a", "agent-b"]
        assert result["message_count"] == 0

    def test_get_orchestration_exists(self):
        storage.create_orchestration("orch-2", "Another purpose")
        result = storage.get_orchestration("orch-2")
        assert result is not None
        assert result["orchestration_id"] == "orch-2"

    def test_get_orchestration_not_found(self):
        result = storage.get_orchestration("nonexistent")
        assert result is None

    def test_list_orchestrations_all(self):
        storage.create_orchestration("a", "Alpha")
        storage.create_orchestration("b", "Beta")
        result = storage.list_orchestrations()
        assert len(result) == 2
        ids = {r["orchestration_id"] for r in result}
        assert ids == {"a", "b"}

    def test_list_orchestrations_by_status(self):
        storage.create_orchestration("x", "X")
        storage.create_orchestration("y", "Y")
        storage.update_orchestration_status("y", "completed", "Done")
        active = storage.list_orchestrations("active")
        completed = storage.list_orchestrations("completed")
        assert len(active) == 1
        assert active[0]["orchestration_id"] == "x"
        assert len(completed) == 1
        assert completed[0]["orchestration_id"] == "y"

    def test_update_orchestration_status(self):
        storage.create_orchestration("z", "Z")
        result = storage.update_orchestration_status("z", "completed", "All done")
        assert result["status"] == "completed"
        assert result["summary"] == "All done"

    def test_update_nonexistent_raises(self):
        import pytest

        with pytest.raises(ValueError, match="not found"):
            storage.update_orchestration_status("ghost", "completed")


class TestMessagePersistence:
    """persist_message / persist_messages / get_conversation."""

    def test_persist_single_message(self):
        storage.create_orchestration("conv-1", "Conversation test")
        result = storage.persist_message("conv-1", "agent-a", "assistant", "Hello world")
        assert result["orchestration_id"] == "conv-1"
        assert result["agent_id"] == "agent-a"
        assert result["role"] == "assistant"
        assert "sequence" in result
        assert "created_at" in result

    def test_persist_message_increments_count(self):
        storage.create_orchestration("conv-2", "Counter test")
        storage.persist_message("conv-2", "a", "user", "msg 1")
        storage.persist_message("conv-2", "b", "assistant", "msg 2")
        orch = storage.get_orchestration("conv-2")
        assert orch["message_count"] == 2

    def test_persist_messages_batch(self):
        storage.create_orchestration("conv-3", "Batch")
        messages = [
            {"agent_id": "a", "role": "user", "content": "First"},
            {"agent_id": "b", "role": "assistant", "content": "Second"},
            {"agent_id": "a", "role": "user", "content": "Third"},
        ]
        results = storage.persist_messages("conv-3", messages)
        assert len(results) == 3

    def test_get_conversation_chronological_order(self):
        storage.create_orchestration("conv-4", "Order test")
        storage.persist_message("conv-4", "a", "user", "First")
        time.sleep(0.001)
        storage.persist_message("conv-4", "b", "assistant", "Second")
        time.sleep(0.001)
        storage.persist_message("conv-4", "a", "user", "Third")
        msgs = storage.get_conversation("conv-4")
        assert len(msgs) == 3
        assert msgs[0]["content"] == "First"
        assert msgs[1]["content"] == "Second"
        assert msgs[2]["content"] == "Third"

    def test_get_conversation_with_limit(self):
        storage.create_orchestration("conv-5", "Limit test")
        for i in range(5):
            time.sleep(0.001)
            storage.persist_message("conv-5", "a", "user", f"msg-{i}")
        msgs = storage.get_conversation("conv-5", limit=3)
        assert len(msgs) == 3

    def test_get_conversation_empty(self):
        msgs = storage.get_conversation("no-such-orch")
        assert msgs == []

    def test_message_metadata_round_trip(self):
        storage.create_orchestration("conv-6", "Metadata test")
        storage.persist_message("conv-6", "a", "tool", "result", metadata={"tool": "search", "hits": 42})
        msgs = storage.get_conversation("conv-6")
        assert len(msgs) == 1
        assert msgs[0]["metadata"] == {"tool": "search", "hits": 42}


class TestRowKeyGeneration:
    """Validate row key format and chronological sorting."""

    def test_row_key_format(self):
        key = storage._msg_row_key()
        assert key.startswith("msg_")
        parts = key.split("_")
        assert len(parts) == 3
        assert len(parts[1]) == 20  # zero-padded epoch microseconds

    def test_row_keys_sort_chronologically(self):
        k1 = storage._msg_row_key()
        time.sleep(0.001)
        k2 = storage._msg_row_key()
        assert k1 < k2, "Later key should sort after earlier key"
