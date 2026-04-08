"""Tests for subconscious.server — MCP tool and resource registrations."""

from __future__ import annotations

import asyncio

from subconscious import storage
from subconscious.server import mcp


class TestMCPToolRegistration:
    """Verify all expected tools are registered on the FastMCP instance."""

    def test_conversation_tools_registered(self):
        expected = {
            "create_orchestration",
            "complete_orchestration",
            "list_orchestrations",
            "persist_message",
            "persist_conversation_turn",
            "get_conversation",
        }
        tools = asyncio.get_event_loop().run_until_complete(mcp.list_tools())
        tool_names = {t.name for t in tools}
        assert expected.issubset(tool_names), f"Missing tools: {expected - tool_names}"

    def test_schema_tools_registered(self):
        expected = {
            "list_schemas",
            "get_schema",
            "store_schema_context",
            "get_schema_context",
            "list_schema_contexts",
        }
        tools = asyncio.get_event_loop().run_until_complete(mcp.list_tools())
        tool_names = {t.name for t in tools}
        assert expected.issubset(tool_names), f"Missing schema tools: {expected - tool_names}"

    def test_expected_resource_templates_registered(self):
        templates = asyncio.get_event_loop().run_until_complete(mcp.list_resource_templates())
        uris = {t.uri_template for t in templates}
        assert "orchestration://{orchestration_id}" in uris
        assert "schema://{schema_name}" in uris
        assert "schema-context://{schema_name}/{context_id}" in uris

    def test_expected_prompts_registered(self):
        prompts = asyncio.get_event_loop().run_until_complete(mcp.list_prompts())
        names = {p.name for p in prompts}
        assert "summarize_conversation" in names


class TestMCPConversationTools:
    """Execute conversation MCP tools through the server."""

    def test_create_orchestration_tool(self):
        result = asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("create_orchestration", {
                "orchestration_id": "mcp-test-1",
                "purpose": "MCP tool test",
                "agents": ["agent-x"],
            })
        )
        assert result is not None

    def test_persist_and_get_conversation_tool(self):
        asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("create_orchestration", {
                "orchestration_id": "mcp-test-2",
                "purpose": "Roundtrip test",
            })
        )
        asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("persist_message", {
                "orchestration_id": "mcp-test-2",
                "agent_id": "agent-a",
                "role": "assistant",
                "content": "Hello from MCP",
            })
        )
        result = asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("get_conversation", {"orchestration_id": "mcp-test-2"})
        )
        assert result is not None

    def test_list_orchestrations_tool(self):
        storage.create_orchestration("list-test", "For listing")
        result = asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("list_orchestrations", {})
        )
        assert result is not None

    def test_persist_conversation_turn_tool(self):
        storage.create_orchestration("turn-test", "Turn test")
        result = asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("persist_conversation_turn", {
                "orchestration_id": "turn-test",
                "messages": [
                    {"agent_id": "a", "role": "user", "content": "Hi"},
                    {"agent_id": "b", "role": "assistant", "content": "Hello"},
                ],
            })
        )
        assert result is not None

    def test_complete_orchestration_tool(self):
        storage.create_orchestration("complete-test", "To complete")
        result = asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("complete_orchestration", {
                "orchestration_id": "complete-test",
                "summary": "All done",
            })
        )
        assert result is not None


class TestMCPSchemaTools:
    """Execute schema MCP tools through the server."""

    def test_list_schemas_tool(self, schemas_dir):
        result = asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("list_schemas", {})
        )
        assert result is not None

    def test_get_schema_tool_known(self, schemas_dir):
        result = asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("get_schema", {"schema_name": "manas"})
        )
        assert result is not None

    def test_get_schema_tool_unknown(self, schemas_dir):
        result = asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("get_schema", {"schema_name": "unknown"})
        )
        assert result is not None

    def test_store_and_get_schema_context_tool(self, schemas_dir):
        doc = {"@type": "Buddhi", "agent_id": "ceo", "name": "Steve Jobs"}
        store_result = asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("store_schema_context", {
                "schema_name": "buddhi",
                "context_id": "ceo",
                "data": doc,
            })
        )
        assert store_result is not None

        get_result = asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("get_schema_context", {
                "schema_name": "buddhi",
                "context_id": "ceo",
            })
        )
        assert get_result is not None

    def test_get_schema_context_not_found(self, schemas_dir):
        result = asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("get_schema_context", {
                "schema_name": "manas",
                "context_id": "ghost",
            })
        )
        assert result is not None

    def test_list_schema_contexts_tool(self, schemas_dir):
        result = asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("list_schema_contexts", {})
        )
        assert result is not None

    def test_list_schema_contexts_filtered(self, schemas_dir):
        from subconscious import schema_storage
        schema_storage.store_schema_context("chitta", "ceo", {"x": 1})
        schema_storage.store_schema_context("chitta", "cfo", {"x": 2})
        result = asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("list_schema_contexts", {"schema_name": "chitta"})
        )
        assert result is not None


class TestMCPResourceExecution:
    """Execute MCP resource reads through the server."""

    def test_orchestration_resource(self):
        storage.create_orchestration("res-test", "Resource test")
        storage.persist_message("res-test", "a", "user", "Test message")
        result = asyncio.get_event_loop().run_until_complete(
            mcp.read_resource("orchestration://res-test")
        )
        assert result is not None

    def test_schema_resource_known(self, schemas_dir):
        result = asyncio.get_event_loop().run_until_complete(
            mcp.read_resource("schema://manas")
        )
        assert result is not None

    def test_schema_resource_unknown(self, schemas_dir):
        result = asyncio.get_event_loop().run_until_complete(
            mcp.read_resource("schema://nonexistent")
        )
        assert result is not None

    def test_schema_context_resource(self, schemas_dir):
        from subconscious import schema_storage
        schema_storage.store_schema_context("ahankara", "ceo", {"identity": "Visionary"})
        result = asyncio.get_event_loop().run_until_complete(
            mcp.read_resource("schema-context://ahankara/ceo")
        )
        assert result is not None

    def test_schema_context_resource_not_found(self, schemas_dir):
        result = asyncio.get_event_loop().run_until_complete(
            mcp.read_resource("schema-context://manas/ghost")
        )
        assert result is not None
