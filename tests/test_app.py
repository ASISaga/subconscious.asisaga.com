"""Tests for subconscious.app — ASGI application (REST API + UI)."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from subconscious import schema_storage, storage
from subconscious.app import create_app


@pytest.fixture()
def app():
    return create_app()


@pytest.fixture()
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health(self, client):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert body["service"] == "subconscious"


class TestHomepageUI:
    @pytest.mark.asyncio
    async def test_homepage_returns_html(self, client):
        resp = await client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Subconscious" in resp.text
        assert "/mcp" in resp.text

    @pytest.mark.asyncio
    async def test_homepage_contains_ui_elements(self, client):
        resp = await client.get("/")
        html = resp.text
        assert "orch-list" in html
        assert "conversation" in html
        assert "/api" in html


class TestOrchestrationsAPI:
    @pytest.mark.asyncio
    async def test_list_empty(self, client):
        resp = await client.get("/api/orchestrations")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_list_with_data(self, client):
        storage.create_orchestration("api-1", "Purpose A")
        storage.create_orchestration("api-2", "Purpose B")
        resp = await client.get("/api/orchestrations")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_list_filter_by_status(self, client):
        storage.create_orchestration("api-3", "Active one")
        storage.create_orchestration("api-4", "Completed one")
        storage.update_orchestration_status("api-4", "completed")
        resp = await client.get("/api/orchestrations?status=completed")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["orchestration_id"] == "api-4"

    @pytest.mark.asyncio
    async def test_get_orchestration(self, client):
        storage.create_orchestration("api-5", "Detail test")
        resp = await client.get("/api/orchestrations/api-5")
        assert resp.status_code == 200
        assert resp.json()["orchestration_id"] == "api-5"

    @pytest.mark.asyncio
    async def test_get_orchestration_not_found(self, client):
        resp = await client.get("/api/orchestrations/nonexistent")
        assert resp.status_code == 404


class TestConversationAPI:
    @pytest.mark.asyncio
    async def test_get_messages(self, client):
        storage.create_orchestration("msg-1", "Messages test")
        storage.persist_message("msg-1", "a", "user", "Hello")
        storage.persist_message("msg-1", "b", "assistant", "Hi there")
        resp = await client.get("/api/orchestrations/msg-1/messages")
        assert resp.status_code == 200
        data = resp.json()
        assert data["orchestration_id"] == "msg-1"
        assert data["total"] == 2
        assert len(data["messages"]) == 2

    @pytest.mark.asyncio
    async def test_get_messages_with_limit(self, client):
        storage.create_orchestration("msg-2", "Limit test")
        for i in range(5):
            storage.persist_message("msg-2", "a", "user", f"msg-{i}")
        resp = await client.get("/api/orchestrations/msg-2/messages?limit=2")
        data = resp.json()
        assert data["total"] == 2

    @pytest.mark.asyncio
    async def test_get_messages_empty(self, client):
        resp = await client.get("/api/orchestrations/empty/messages")
        assert resp.status_code == 200
        data = resp.json()
        assert data["messages"] == []


class TestSchemasAPI:
    @pytest.mark.asyncio
    async def test_list_schemas(self, client, schemas_dir):
        resp = await client.get("/api/schemas")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 7
        names = {s["name"] for s in data}
        assert "manas" in names
        assert "buddhi" in names
        assert "chitta" in names

    @pytest.mark.asyncio
    async def test_get_schema_known(self, client, schemas_dir):
        resp = await client.get("/api/schemas/manas")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Manas — Agent Memory State"

    @pytest.mark.asyncio
    async def test_get_schema_not_found(self, client, schemas_dir):
        resp = await client.get("/api/schemas/unknown")
        assert resp.status_code == 404
        body = resp.json()
        assert "error" in body
        assert "available" in body


class TestSchemaContextsAPI:
    @pytest.mark.asyncio
    async def test_list_schema_contexts_empty(self, client):
        resp = await client.get("/api/schema-contexts")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_store_and_get_schema_context(self, client, schemas_dir):
        doc = {"@type": "Buddhi", "agent_id": "ceo", "name": "Steve Jobs"}
        put_resp = await client.put("/api/schema-contexts/buddhi/ceo", json=doc)
        assert put_resp.status_code == 200
        put_data = put_resp.json()
        assert put_data["schema_name"] == "buddhi"
        assert put_data["context_id"] == "ceo"

        get_resp = await client.get("/api/schema-contexts/buddhi/ceo")
        assert get_resp.status_code == 200
        get_data = get_resp.json()
        assert get_data["data"] == doc

    @pytest.mark.asyncio
    async def test_get_schema_context_not_found(self, client):
        resp = await client.get("/api/schema-contexts/manas/ghost")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_schema_contexts_after_store(self, client, schemas_dir):
        schema_storage.store_schema_context("manas", "ceo", {})
        schema_storage.store_schema_context("manas", "cfo", {})
        resp = await client.get("/api/schema-contexts?schema=manas")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_store_schema_context_invalid_json(self, client):
        resp = await client.put(
            "/api/schema-contexts/buddhi/ceo",
            content=b"not-json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400
