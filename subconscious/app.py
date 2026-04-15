"""Subconscious landing page.

This module provides :func:`get_app_html` — the HTML landing page served at
``/`` by the Azure Functions host.  All data access is exposed through the
MCP endpoint at ``/mcp`` using FastMCP tools, resources, and the
``Conversations`` MCP App.
"""

from __future__ import annotations


def get_app_html() -> str:
    """Return the Subconscious landing page HTML."""
    return _APP_HTML


_APP_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Subconscious — MCP Server</title>
<style>
  :root {
    --bg: #0f1117; --surface: #1a1d27; --surface2: #242836;
    --border: #2e3348; --text: #e4e6f0; --muted: #8b8fa3;
    --accent: #6c63ff; --success: #22c55e;
    --font: 'Segoe UI', system-ui, -apple-system, sans-serif;
    --mono: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: var(--font); background: var(--bg); color: var(--text);
         display: flex; align-items: center; justify-content: center;
         min-height: 100vh; padding: 24px; }
  .card { background: var(--surface); border: 1px solid var(--border);
          border-radius: 12px; padding: 40px 48px; max-width: 640px; width: 100%; }
  h1 { font-size: 1.5rem; font-weight: 700; margin-bottom: 8px; }
  p { color: var(--muted); line-height: 1.6; margin-bottom: 20px; }
  .endpoint { background: var(--surface2); border: 1px solid var(--border);
              border-radius: 8px; padding: 12px 16px; margin: 16px 0; }
  .endpoint code { font-family: var(--mono); color: var(--accent); font-size: .9rem; }
  .endpoint small { display: block; color: var(--muted); font-size: .78rem; margin-top: 4px; }
  h2 { font-size: 1rem; font-weight: 600; margin: 24px 0 12px; color: var(--text); }
  ul { padding-left: 20px; }
  li { color: var(--muted); line-height: 1.8; font-size: .9rem; }
  li code { font-family: var(--mono); color: var(--accent); font-size: .85rem; }
  .tag { display: inline-block; background: rgba(108,99,255,.15); color: var(--accent);
         border-radius: 4px; padding: 2px 8px; font-size: .75rem; font-weight: 600;
         margin-right: 6px; }
</style>
</head>
<body>
<div class="card">
  <h1>&#x1f9e0; Subconscious</h1>
  <p>Multi-agent conversation persistence and schema context server,
     powered by FastMCP on Azure Functions.</p>

  <h2>MCP Endpoint</h2>
  <div class="endpoint">
    <code>/mcp</code>
    <small>Connect your MCP client (Claude Desktop, Copilot, etc.) to this endpoint.</small>
  </div>

  <h2>Available via MCP</h2>
  <ul>
    <li><span class="tag">App</span><code>show_conversations</code> — rich Prefab UI for browsing orchestrations</li>
    <li><span class="tag">Tool</span><code>create_orchestration</code>, <code>list_orchestrations</code>, <code>get_conversation</code></li>
    <li><span class="tag">Tool</span><code>persist_message</code>, <code>persist_conversation_turn</code></li>
    <li><span class="tag">Tool</span><code>list_schemas</code>, <code>get_schema</code></li>
    <li><span class="tag">Tool</span><code>store_schema_context</code>, <code>get_schema_context</code></li>
    <li><span class="tag">Resource</span><code>orchestration://&lt;id&gt;</code>, <code>schema://&lt;name&gt;</code></li>
    <li><span class="tag">Prompt</span><code>summarize_conversation</code></li>
  </ul>

  <h2>Data Format</h2>
  <p style="margin-bottom:0">All conversation and orchestration data is exchanged as
    <strong style="color:var(--text)">Schema.org JSON-LD</strong>
    (<code>schema:Action</code>, <code>schema:Conversation</code>, <code>schema:Message</code>).
  </p>
</div>
</body>
</html>
"""

