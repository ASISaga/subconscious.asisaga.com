"""ASGI application factory — combines MCP endpoint, REST API, and web UI.

The application is structured as a single Starlette ASGI app that mounts:

* ``/mcp``  — Streamable-HTTP MCP endpoint (FastMCP)
* ``/api``  — Lightweight JSON API consumed by the built-in UI
* ``/``     — Single-page MCP Apps UI for browsing orchestrations
"""

from __future__ import annotations

import logging

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Mount, Route

from subconscious import schema_storage, storage
from subconscious.server import mcp

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# REST API handlers — orchestrations (consumed by the built-in UI)
# ---------------------------------------------------------------------------

async def api_list_orchestrations(request: Request) -> JSONResponse:
    """``GET /api/orchestrations[?status=active]``"""
    status = request.query_params.get("status")
    data = storage.list_orchestrations(status)
    return JSONResponse(data)


async def api_get_orchestration(request: Request) -> JSONResponse:
    """``GET /api/orchestrations/{oid}``"""
    oid = request.path_params["oid"]
    data = storage.get_orchestration(oid)
    if data is None:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return JSONResponse(data)


async def api_get_conversation(request: Request) -> JSONResponse:
    """``GET /api/orchestrations/{oid}/messages[?limit=200]``"""
    oid = request.path_params["oid"]
    limit = int(request.query_params.get("limit", "200"))
    messages = storage.get_conversation(oid, limit=limit)
    return JSONResponse({"orchestration_id": oid, "messages": messages, "total": len(messages)})


# ---------------------------------------------------------------------------
# REST API handlers — schema definitions (read-only)
# ---------------------------------------------------------------------------

async def api_list_schemas(request: Request) -> JSONResponse:
    """``GET /api/schemas``"""
    return JSONResponse(schema_storage.list_schemas())


async def api_get_schema(request: Request) -> JSONResponse:
    """``GET /api/schemas/{name}``"""
    name = request.path_params["name"]
    data = schema_storage.get_schema(name)
    if data is None:
        available = list(schema_storage.SCHEMA_REGISTRY.keys())
        return JSONResponse({"error": "Schema not found", "available": available}, status_code=404)
    return JSONResponse(data)


# ---------------------------------------------------------------------------
# REST API handlers — schema contexts
# ---------------------------------------------------------------------------

async def api_list_schema_contexts(request: Request) -> JSONResponse:
    """``GET /api/schema-contexts[?schema=manas]``"""
    schema_name = request.query_params.get("schema")
    data = schema_storage.list_schema_contexts(schema_name)
    return JSONResponse(data)


async def api_get_schema_context(request: Request) -> JSONResponse:
    """``GET /api/schema-contexts/{schema_name}/{context_id}``"""
    schema_name = request.path_params["schema_name"]
    context_id = request.path_params["context_id"]
    result = schema_storage.get_schema_context(schema_name, context_id)
    if result is None:
        return JSONResponse({"error": "Schema context not found"}, status_code=404)
    return JSONResponse(result)


async def api_store_schema_context(request: Request) -> JSONResponse:
    """``PUT /api/schema-contexts/{schema_name}/{context_id}``"""
    schema_name = request.path_params["schema_name"]
    context_id = request.path_params["context_id"]
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)
    result = schema_storage.store_schema_context(schema_name, context_id, body)
    return JSONResponse(result)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

async def api_health(request: Request) -> JSONResponse:
    """``GET /api/health``"""
    return JSONResponse({"status": "healthy", "service": "subconscious"})


# ---------------------------------------------------------------------------
# MCP Apps UI (single-page HTML application)
# ---------------------------------------------------------------------------

async def homepage(request: Request) -> HTMLResponse:
    """Serve the built-in MCP Apps UI."""
    return HTMLResponse(_APP_HTML)


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_app() -> Starlette:
    """Build and return the composite ASGI application."""
    mcp_app = mcp.http_app()

    routes = [
        Route("/", homepage),
        Route("/api/health", api_health),
        Route("/api/orchestrations", api_list_orchestrations),
        Route("/api/orchestrations/{oid}", api_get_orchestration),
        Route("/api/orchestrations/{oid}/messages", api_get_conversation),
        Route("/api/schemas", api_list_schemas),
        Route("/api/schemas/{name}", api_get_schema),
        Route("/api/schema-contexts", api_list_schema_contexts),
        Route("/api/schema-contexts/{schema_name}/{context_id}", api_get_schema_context,
              methods=["GET"]),
        Route("/api/schema-contexts/{schema_name}/{context_id}", api_store_schema_context,
              methods=["PUT"]),
        Mount("/mcp", app=mcp_app),
    ]
    return Starlette(routes=routes)


# ---------------------------------------------------------------------------
# Embedded HTML UI
# ---------------------------------------------------------------------------

_APP_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Subconscious — MCP Apps</title>
<style>
  :root {
    --bg: #0f1117; --surface: #1a1d27; --surface2: #242836;
    --border: #2e3348; --text: #e4e6f0; --muted: #8b8fa3;
    --accent: #6c63ff; --accent-dim: #4a4380; --success: #22c55e;
    --warn: #f59e0b; --error: #ef4444;
    --font: 'Segoe UI', system-ui, -apple-system, sans-serif;
    --mono: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: var(--font); background: var(--bg); color: var(--text);
         display: flex; height: 100vh; overflow: hidden; }

  /* Sidebar */
  #sidebar { width: 340px; min-width: 260px; background: var(--surface);
             border-right: 1px solid var(--border); display: flex; flex-direction: column; }
  #sidebar header { padding: 20px; border-bottom: 1px solid var(--border); }
  #sidebar header h1 { font-size: 1.15rem; font-weight: 600; }
  #sidebar header p { font-size: .78rem; color: var(--muted); margin-top: 4px; }
  #filter-bar { padding: 12px 16px; display: flex; gap: 8px; border-bottom: 1px solid var(--border); }
  #filter-bar select, #filter-bar input {
    flex: 1; background: var(--surface2); color: var(--text); border: 1px solid var(--border);
    border-radius: 6px; padding: 7px 10px; font-size: .82rem; outline: none;
  }
  #filter-bar select:focus, #filter-bar input:focus { border-color: var(--accent); }
  #orch-list { flex: 1; overflow-y: auto; padding: 8px; }
  .orch-card { padding: 12px 14px; border-radius: 8px; cursor: pointer;
               margin-bottom: 4px; transition: background .15s; }
  .orch-card:hover { background: var(--surface2); }
  .orch-card.active { background: var(--accent-dim); }
  .orch-card h3 { font-size: .88rem; font-weight: 500; white-space: nowrap;
                  overflow: hidden; text-overflow: ellipsis; }
  .orch-card .meta { font-size: .73rem; color: var(--muted); margin-top: 4px;
                     display: flex; gap: 10px; align-items: center; }
  .badge { display: inline-block; padding: 2px 7px; border-radius: 4px;
           font-size: .68rem; font-weight: 600; text-transform: uppercase; }
  .badge-active { background: rgba(108,99,255,.2); color: var(--accent); }
  .badge-completed { background: rgba(34,197,94,.15); color: var(--success); }
  .badge-failed { background: rgba(239,68,68,.15); color: var(--error); }

  /* Main panel */
  #main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
  #main header { padding: 18px 24px; border-bottom: 1px solid var(--border);
                 display: flex; justify-content: space-between; align-items: center; }
  #main header h2 { font-size: 1.05rem; font-weight: 600; }
  #main header .info { font-size: .78rem; color: var(--muted); }
  #conversation { flex: 1; overflow-y: auto; padding: 20px 24px; }
  #placeholder { display: flex; align-items: center; justify-content: center;
                 height: 100%; color: var(--muted); font-size: .95rem; }

  /* Messages */
  .msg { margin-bottom: 16px; padding: 14px 18px; border-radius: 10px;
         background: var(--surface); border: 1px solid var(--border); }
  .msg .msg-header { display: flex; justify-content: space-between; margin-bottom: 6px; }
  .msg .agent { font-size: .82rem; font-weight: 600; color: var(--accent); }
  .msg .role { font-size: .72rem; color: var(--muted); text-transform: uppercase;
               background: var(--surface2); padding: 2px 6px; border-radius: 3px; }
  .msg .content { font-size: .88rem; line-height: 1.55; white-space: pre-wrap; word-break: break-word; }
  .msg .ts { font-size: .7rem; color: var(--muted); margin-top: 6px; }

  /* Connection bar */
  #conn-bar { padding: 10px 24px; border-top: 1px solid var(--border);
              background: var(--surface); font-size: .78rem; color: var(--muted);
              display: flex; justify-content: space-between; align-items: center; }
  #conn-bar code { font-family: var(--mono); color: var(--accent); background: var(--surface2);
                   padding: 2px 8px; border-radius: 4px; font-size: .76rem; }
  .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-right: 6px; }
  .dot-ok { background: var(--success); }
  .dot-err { background: var(--error); }

  /* Empty state */
  .empty { text-align: center; padding: 40px 20px; color: var(--muted); }
  .empty svg { width: 48px; height: 48px; margin-bottom: 12px; opacity: .4; }

  /* Scrollbar */
  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
</style>
</head>
<body>

<!-- Sidebar -->
<div id="sidebar">
  <header>
    <h1 aria-label="Subconscious">&#x1f9e0; Subconscious</h1>
    <p>Multi-Agent Conversation &amp; Schema Context Persistence</p>
  </header>
  <div id="filter-bar">
    <select id="status-filter">
      <option value="">All</option>
      <option value="active">Active</option>
      <option value="completed">Completed</option>
      <option value="failed">Failed</option>
    </select>
    <input id="search" type="text" placeholder="Search&#x2026;"/>
  </div>
  <div id="orch-list"></div>
</div>

<!-- Main panel -->
<div id="main">
  <header id="main-header" style="display:none">
    <div>
      <h2 id="orch-title">—</h2>
      <div class="info" id="orch-info"></div>
    </div>
    <div id="orch-badge"></div>
  </header>
  <div id="conversation">
    <div id="placeholder">
      <div class="empty">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"
             stroke="currentColor" stroke-width="1.5">
          <path stroke-linecap="round" stroke-linejoin="round"
                d="M20.25 8.511c.884.284 1.5 1.128 1.5 2.097v4.286c0 1.136-.847
                   2.1-1.98 2.193-.34.027-.68.052-1.02.072v3.091l-3-3a49.5 49.5 0
                   01-4.02-.163 2.115 2.115 0 01-.825-.242m9.345-8.334a2.126 2.126 0
                   00-.476-.095 48.64 48.64 0 00-8.048 0c-1.131.094-1.976 1.057-1.976
                   2.192v4.286c0 .837.46 1.58 1.155 1.951m9.345-8.334V6.637c0-1.621
                   -1.152-3.026-2.76-3.235A48.455 48.455 0 0011.25 3c-2.115
                   0-4.198.137-6.24.402-1.608.209-2.76 1.614-2.76 3.235v6.226c0
                   1.621 1.152 3.026 2.76 3.235.577.075 1.157.14 1.74.194V21l4.155
                   -4.155"/>
        </svg>
        <p>Select an orchestration to view its conversation</p>
        <p style="margin-top:8px;font-size:.78rem">
          MCP endpoint: <code style="font-family:var(--mono);color:var(--accent)">/mcp</code>
        </p>
      </div>
    </div>
  </div>
  <div id="conn-bar">
    <span><span class="dot dot-ok" id="health-dot"></span>
      MCP endpoint: <code>/mcp</code></span>
    <span id="msg-count"></span>
  </div>
</div>

<script>
const API = '/api';
let orchestrations = [];
let selectedId = null;
let refreshTimer = null;

async function fetchJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(r.statusText);
  return r.json();
}

function badgeHTML(status) {
  const cls = {active:'badge-active',completed:'badge-completed',failed:'badge-failed'}[status]||'badge-active';
  return `<span class="badge ${cls}">${status}</span>`;
}

function timeAgo(iso) {
  if (!iso) return '';
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return s + 's ago';
  if (s < 3600) return Math.floor(s/60) + 'm ago';
  if (s < 86400) return Math.floor(s/3600) + 'h ago';
  return Math.floor(s/86400) + 'd ago';
}

async function loadOrchestrations() {
  const status = document.getElementById('status-filter').value;
  const url = status ? `${API}/orchestrations?status=${status}` : `${API}/orchestrations`;
  try {
    orchestrations = await fetchJSON(url);
    renderList();
  } catch(e) {
    document.getElementById('orch-list').innerHTML =
      '<div class="empty"><p>Unable to load orchestrations</p></div>';
  }
}

function renderList() {
  const q = document.getElementById('search').value.toLowerCase();
  const filtered = orchestrations.filter(o =>
    !q || o.orchestration_id.toLowerCase().includes(q) || (o.purpose||'').toLowerCase().includes(q)
  );
  const el = document.getElementById('orch-list');
  if (!filtered.length) {
    el.innerHTML = '<div class="empty"><p>No orchestrations found</p></div>';
    return;
  }
  el.innerHTML = filtered.map(o => `
    <div class="orch-card ${o.orchestration_id===selectedId?'active':''}"
         onclick="selectOrch('${o.orchestration_id}')">
      <h3 title="${o.orchestration_id}">${o.purpose || o.orchestration_id}</h3>
      <div class="meta">
        ${badgeHTML(o.status)}
        <span>${o.message_count} msgs</span>
        <span>${timeAgo(o.updated_at)}</span>
      </div>
    </div>
  `).join('');
}

async function selectOrch(id) {
  selectedId = id;
  renderList();
  document.getElementById('main-header').style.display = 'flex';
  const orch = orchestrations.find(o => o.orchestration_id === id);
  document.getElementById('orch-title').textContent = orch ? (orch.purpose || id) : id;
  document.getElementById('orch-info').textContent = `ID: ${id}`;
  document.getElementById('orch-badge').innerHTML = orch ? badgeHTML(orch.status) : '';
  await loadMessages(id);
}

async function loadMessages(id) {
  const conv = document.getElementById('conversation');
  try {
    const data = await fetchJSON(`${API}/orchestrations/${id}/messages`);
    document.getElementById('msg-count').textContent = `${data.total} messages`;
    if (!data.messages.length) {
      conv.innerHTML = '<div class="empty"><p>No messages yet</p></div>';
      return;
    }
    conv.innerHTML = data.messages.map(m => `
      <div class="msg">
        <div class="msg-header">
          <span class="agent">${m.agent_id}</span>
          <span class="role">${m.role}</span>
        </div>
        <div class="content">${escapeHTML(m.content)}</div>
        <div class="ts">${m.created_at}</div>
      </div>
    `).join('');
    conv.scrollTop = conv.scrollHeight;
  } catch(e) {
    conv.innerHTML = '<div class="empty"><p>Failed to load conversation</p></div>';
  }
}

function escapeHTML(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

async function checkHealth() {
  const dot = document.getElementById('health-dot');
  try {
    await fetchJSON(`${API}/health`);
    dot.className = 'dot dot-ok';
  } catch {
    dot.className = 'dot dot-err';
  }
}

// Initialise
document.getElementById('status-filter').addEventListener('change', loadOrchestrations);
document.getElementById('search').addEventListener('input', renderList);
loadOrchestrations();
checkHealth();
refreshTimer = setInterval(() => {
  loadOrchestrations();
  if (selectedId) loadMessages(selectedId);
  checkHealth();
}, 15000);
</script>
</body>
</html>
"""
