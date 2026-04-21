"""Tests for server — MCP tool and resource registrations."""

from __future__ import annotations

import asyncio
import json

from server import mcp
from storage import conversations as storage
from storage import schemas as schema_storage


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
            "initialize_schema_contexts",
            # dedicated semantic mind-layer tools
            "get_chitta", "set_chitta",
            "get_ahankara", "set_ahankara",
            "get_buddhi", "set_buddhi",
            "get_action_plan", "set_action_plan",
            "get_manas", "set_manas",
            "get_integrity", "set_integrity",
            "get_responsibilities", "set_responsibilities",
            "get_entity_content", "set_entity_content",
            "get_entity_context", "set_entity_context",
        }
        tools = asyncio.get_event_loop().run_until_complete(mcp.list_tools())
        tool_names = {t.name for t in tools}
        assert expected.issubset(tool_names), f"Missing schema tools: {expected - tool_names}"

    def test_generic_dimension_tools_removed(self):
        """Verify the generic-dimension tools are no longer registered."""
        tools = asyncio.get_event_loop().run_until_complete(mcp.list_tools())
        tool_names = {t.name for t in tools}
        assert "get_agent_state" not in tool_names
        assert "set_agent_state" not in tool_names
        assert "get_dimension_schema" not in tool_names

    def test_mcp_apps_tools_registered(self):
        """show_conversations is a model-visible @mcp.tool(); fetch_* are app-internal."""
        tools = asyncio.get_event_loop().run_until_complete(mcp.list_tools())
        tool_names = {t.name for t in tools}
        # show_conversations is registered directly on mcp — model-visible
        assert "show_conversations" in tool_names
        # fetch_orchestrations and fetch_conversation are registered on conversations_app
        # (FastMCPApp) — they are app-internal and must NOT be exposed to the model
        assert "fetch_orchestrations" not in tool_names
        assert "fetch_conversation" not in tool_names

    def test_expected_resource_templates_registered(self):
        templates = asyncio.get_event_loop().run_until_complete(mcp.list_resource_templates())
        uris = {t.uri_template for t in templates}
        assert "orchestration://{orchestration_id}" in uris
        assert "schema://{schema_name}" in uris
        assert "schema-context://{schema_name}/{context_id}" in uris
        assert "mind://{agent_id}/{dimension}" in uris

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

    def test_get_conversation_returns_jsonld(self):
        storage.create_orchestration("jsonld-test", "JSON-LD test")
        storage.persist_message("jsonld-test", "ceo", "user", "Strategic update")
        result = asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("get_conversation", {"orchestration_id": "jsonld-test"})
        )
        data = json.loads(result.content[0].text)
        assert data["@type"] == "Conversation"
        assert data["@context"] == "https://schema.org/"
        assert data["orchestration_id"] == "jsonld-test"
        assert data["total"] == 1
        msg = data["messages"][0]
        assert msg["@type"] == "Message"
        assert msg["text"] == "Strategic update"

    def test_list_orchestrations_returns_jsonld(self):
        storage.create_orchestration("lo-test", "List test")
        result = asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("list_orchestrations", {})
        )
        data = json.loads(result.content[0].text)
        assert isinstance(data, list)
        assert data[0]["@type"] == "Action"
        assert data[0]["@context"] == "https://schema.org/"

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


class TestMCPAppsConversations:
    """Verify the Conversations FastMCPApp backend tools work correctly.

    ``fetch_orchestrations`` and ``fetch_conversation`` have visibility=[\"app\"]
    and are intentionally hidden from the model.  We test them by calling the
    registered Python functions directly.
    """

    def test_load_orchestrations_returns_jsonld(self):
        from server.tools import fetch_orchestrations
        storage.create_orchestration("app-lo-1", "App test orch")
        data = fetch_orchestrations()
        assert isinstance(data, list)
        assert data[0]["@type"] == "Action"
        assert "@context" in data[0]

    def test_load_orchestrations_filter_by_status(self):
        from server.tools import fetch_orchestrations
        storage.create_orchestration("app-active", "Active orch")
        storage.create_orchestration("app-done", "Completed orch")
        storage.update_orchestration_status("app-done", "completed")
        data = fetch_orchestrations(status="completed")
        ids = [o["orchestration_id"] for o in data]
        assert "app-done" in ids
        assert "app-active" not in ids

    def test_load_conversation_returns_jsonld_conversation(self):
        from server.tools import fetch_conversation
        storage.create_orchestration("app-conv-1", "App conv test")
        storage.persist_message("app-conv-1", "cfo", "assistant", "Budget is on track.")
        data = fetch_conversation("app-conv-1")
        assert data["@type"] == "Conversation"
        assert data["@context"] == "https://schema.org/"
        assert data["orchestration_id"] == "app-conv-1"
        assert data["total"] == 1
        msg = data["messages"][0]
        assert msg["@type"] == "Message"
        assert msg["sender"]["identifier"] == "cfo"

    def test_load_conversation_empty(self):
        from server.tools import fetch_conversation
        storage.create_orchestration("app-empty", "Empty conv")
        data = fetch_conversation("app-empty")
        assert data["total"] == 0
        assert data["messages"] == []

    def test_show_conversations_returns_jsonld_itemlist(self):
        """show_conversations is a regular MCP tool returning Schema.org ItemList JSON-LD."""
        from server.tools import show_conversations
        data = show_conversations()
        assert data["@type"] == "ItemList"
        assert data["@context"] == "https://schema.org/"
        assert "view_url" in data
        assert data["view_url"].startswith("/view/conversations")
        assert isinstance(data["itemListElement"], list)

    def test_show_conversations_filtered_view_url(self):
        """show_conversations with status= passes it through to the view_url."""
        from server.tools import show_conversations
        data = show_conversations(status="active")
        assert "status=active" in data["view_url"]


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
        schema_storage.store_schema_context("chitta", "ceo", {"x": 1})
        schema_storage.store_schema_context("chitta", "cfo", {"x": 2})
        result = asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("list_schema_contexts", {"schema_name": "chitta"})
        )
        assert result is not None

    def test_initialize_schema_contexts_tool(self):
        result = asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("initialize_schema_contexts", {})
        )
        payload = json.loads(result.content[0].text)
        assert "initialized" in payload
        assert "reason" in payload
        assert "seeded" in payload


class TestMCPResourceExecution:
    """Execute MCP resource reads through the server."""

    def test_orchestration_resource_returns_jsonld(self):
        storage.create_orchestration("res-test", "Resource test")
        storage.persist_message("res-test", "a", "user", "Test message")
        result = asyncio.get_event_loop().run_until_complete(
            mcp.read_resource("orchestration://res-test")
        )
        data = json.loads(result.contents[0].content)
        assert data["@type"] == "Action"
        assert "@context" in data
        assert "object" in data
        assert data["object"]["@type"] == "Conversation"

    def test_orchestration_resource_not_found(self):
        result = asyncio.get_event_loop().run_until_complete(
            mcp.read_resource("orchestration://nonexistent-orch")
        )
        data = json.loads(result.contents[0].content)
        assert "error" in data

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

    def test_agent_mind_resource(self, schemas_dir):
        """mind://{agent_id}/{dimension} resource returns the stored state."""
        schema_storage.store_schema_context("chitta", "ceo", {"pure_intelligence": "cosmic"})
        result = asyncio.get_event_loop().run_until_complete(
            mcp.read_resource("mind://ceo/chitta")
        )
        data = json.loads(result.contents[0].content)
        assert data["data"]["pure_intelligence"] == "cosmic"

    def test_agent_mind_resource_not_found(self, schemas_dir):
        """mind:// resource returns error dict when state does not exist."""
        result = asyncio.get_event_loop().run_until_complete(
            mcp.read_resource("mind://ghost/manas")
        )
        data = json.loads(result.contents[0].content)
        assert "error" in data

    def test_agent_mind_resource_unknown_dimension(self, schemas_dir):
        """mind:// resource returns error dict for an unrecognised dimension."""
        result = asyncio.get_event_loop().run_until_complete(
            mcp.read_resource("mind://ceo/unknowndimension")
        )
        data = json.loads(result.contents[0].content)
        assert "error" in data



class TestDedicatedMindLayerTools:
    """Dedicated semantic MCP tools — one get/set pair per mind layer."""

    # ── Four primary mind layers ──────────────────────────────────────────────

    def test_chitta_round_trip(self, schemas_dir):
        """set_chitta + get_chitta persist and retrieve correctly."""
        doc = {"@type": "Chitta", "agent_id": "cfo"}
        asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("set_chitta", {"agent_id": "cfo", "data": doc})
        )
        result = asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("get_chitta", {"agent_id": "cfo"})
        )
        payload = json.loads(result.content[0].text)
        assert payload["data"] == doc
        assert payload["context_id"] == "cfo"
        assert payload["schema_name"] == "chitta"

    def test_ahankara_round_trip(self, schemas_dir):
        """set_ahankara + get_ahankara persist and retrieve correctly."""
        doc = {"@type": "Ahankara", "identity": "Visionary"}
        asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("set_ahankara", {"agent_id": "ceo", "data": doc})
        )
        result = asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("get_ahankara", {"agent_id": "ceo"})
        )
        payload = json.loads(result.content[0].text)
        assert payload["data"] == doc
        assert payload["schema_name"] == "ahankara"

    def test_buddhi_round_trip(self, schemas_dir):
        """set_buddhi + get_buddhi persist and retrieve correctly."""
        doc = {"@type": "Buddhi", "domain": "finance"}
        asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("set_buddhi", {"agent_id": "cfo", "data": doc})
        )
        result = asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("get_buddhi", {"agent_id": "cfo"})
        )
        payload = json.loads(result.content[0].text)
        assert payload["data"] == doc
        assert payload["schema_name"] == "buddhi"

    def test_manas_round_trip(self, schemas_dir):
        """set_manas + get_manas persist and retrieve correctly."""
        doc = {"@type": "Manas", "focus": "Q2 planning"}
        asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("set_manas", {"agent_id": "cto", "data": doc})
        )
        result = asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("get_manas", {"agent_id": "cto"})
        )
        payload = json.loads(result.content[0].text)
        assert payload["data"] == doc
        assert payload["schema_name"] == "manas"

    # ── Supporting mind layers ────────────────────────────────────────────────

    def test_action_plan_round_trip(self, schemas_dir):
        """set_action_plan + get_action_plan persist and retrieve correctly."""
        doc = {"@type": "ActionPlan", "goals": ["launch product"]}
        asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("set_action_plan", {"agent_id": "ceo", "data": doc})
        )
        result = asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("get_action_plan", {"agent_id": "ceo"})
        )
        payload = json.loads(result.content[0].text)
        assert payload["data"] == doc
        assert payload["schema_name"] == "action-plan"

    def test_integrity_round_trip(self, schemas_dir):
        """set_integrity + get_integrity persist and retrieve correctly."""
        doc = {"@type": "Integrity", "score": 0.95}
        asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("set_integrity", {"agent_id": "coo", "data": doc})
        )
        result = asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("get_integrity", {"agent_id": "coo"})
        )
        payload = json.loads(result.content[0].text)
        assert payload["data"] == doc
        assert payload["schema_name"] == "integrity"

    def test_responsibilities_round_trip(self, schemas_dir):
        """set_responsibilities + get_responsibilities persist and retrieve correctly."""
        doc = {"@type": "RoleResponsibilities", "role": "Entrepreneur"}
        asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("set_responsibilities", {
                "agent_id": "ceo",
                "role": "entrepreneur",
                "data": doc,
            })
        )
        result = asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("get_responsibilities", {
                "agent_id": "ceo",
                "role": "entrepreneur",
            })
        )
        payload = json.loads(result.content[0].text)
        assert payload["data"] == doc
        assert payload["schema_name"] == "responsibilities"
        assert payload["context_id"] == "ceo/entrepreneur"

    def test_entity_content_round_trip(self, schemas_dir):
        """set_entity_content + get_entity_content persist and retrieve correctly."""
        doc = {"@type": "SagaEntity", "current_signals": ["signal-1"]}
        asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("set_entity_content", {
                "agent_id": "cmo",
                "entity": "company",
                "data": doc,
            })
        )
        result = asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("get_entity_content", {
                "agent_id": "cmo",
                "entity": "company",
            })
        )
        payload = json.loads(result.content[0].text)
        assert payload["data"] == doc
        assert payload["schema_name"] == "entity-content"
        assert payload["context_id"] == "cmo/company"

    def test_entity_context_round_trip(self, schemas_dir):
        """set_entity_context + get_entity_context persist and retrieve correctly."""
        doc = {"@type": "SagaEntity", "stable_definition": "immutable truth"}
        asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("set_entity_context", {
                "agent_id": "cso",
                "entity": "business-infinity",
                "data": doc,
            })
        )
        result = asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("get_entity_context", {
                "agent_id": "cso",
                "entity": "business-infinity",
            })
        )
        payload = json.loads(result.content[0].text)
        assert payload["data"] == doc
        assert payload["schema_name"] == "entity-context"
        assert payload["context_id"] == "cso/business-infinity"

    # ── Not-found errors ──────────────────────────────────────────────────────

    def test_get_chitta_not_found(self, schemas_dir):
        result = asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("get_chitta", {"agent_id": "ghost"})
        )
        payload = json.loads(result.content[0].text)
        assert "error" in payload

    def test_get_responsibilities_not_found(self, schemas_dir):
        result = asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("get_responsibilities", {"agent_id": "ghost", "role": "entrepreneur"})
        )
        payload = json.loads(result.content[0].text)
        assert "error" in payload

    def test_get_entity_content_not_found(self, schemas_dir):
        result = asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("get_entity_content", {"agent_id": "ghost", "entity": "company"})
        )
        payload = json.loads(result.content[0].text)
        assert "error" in payload

    def test_get_entity_context_not_found(self, schemas_dir):
        result = asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("get_entity_context", {"agent_id": "ghost", "entity": "company"})
        )
        payload = json.loads(result.content[0].text)
        assert "error" in payload

    # ── company_id scoping ────────────────────────────────────────────────────

    def test_company_id_scoping(self, schemas_dir):
        """company_id scoping is propagated correctly through the semantic tools."""
        doc = {"@type": "Manas", "scoped": True}
        asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("set_manas", {"agent_id": "ceo", "data": doc, "company_id": "asisaga"})
        )
        result = asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("get_manas", {"agent_id": "ceo", "company_id": "asisaga"})
        )
        assert json.loads(result.content[0].text)["data"] == doc

        # Unscoped read must miss the scoped row
        miss = asyncio.get_event_loop().run_until_complete(
            mcp.call_tool("get_manas", {"agent_id": "ceo"})
        )
        assert "error" in json.loads(miss.content[0].text)
