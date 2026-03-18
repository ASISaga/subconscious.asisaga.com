"""Tests for subconscious.server — MCP tool and resource registrations."""

from __future__ import annotations

import asyncio

from subconscious import storage
from subconscious.server import mcp


class TestMCPToolRegistration:
    """Verify all expected tools are registered on the FastMCP instance."""

    def test_expected_tools_registered(self):
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

    def test_expected_resource_templates_registered(self):
        templates = asyncio.get_event_loop().run_until_complete(mcp.list_resource_templates())
        uris = {t.uri_template for t in templates}
        assert "orchestration://{orchestration_id}" in uris

    def test_expected_prompts_registered(self):
        prompts = asyncio.get_event_loop().run_until_complete(mcp.list_prompts())
        names = {p.name for p in prompts}
        assert "summarize_conversation" in names


class TestMCPToolExecution:
    """Execute MCP tools through the server and validate responses."""

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
        # Create orchestration first
        asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("create_orchestration", {
                "orchestration_id": "mcp-test-2",
                "purpose": "Roundtrip test",
            })
        )
        # Persist a message
        asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("persist_message", {
                "orchestration_id": "mcp-test-2",
                "agent_id": "agent-a",
                "role": "assistant",
                "content": "Hello from MCP",
            })
        )
        # Get conversation
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


class TestMCPResourceExecution:
    """Execute MCP resource reads through the server."""

    def test_orchestration_resource(self):
        storage.create_orchestration("res-test", "Resource test")
        storage.persist_message("res-test", "a", "user", "Test message")
        result = asyncio.get_event_loop().run_until_complete(
            mcp.read_resource("orchestration://res-test")
        )
        assert result is not None
