"""HTML5/CSS3 client-side templates for the Subconscious web UI.

Two pages are provided:

* :func:`conversations_page` — Single-page application that fetches Schema.org
  JSON-LD from ``/data/orchestrations`` and renders conversations entirely in
  the browser using vanilla JavaScript.  No React, no server-side templating.

* :func:`monitor_page` — Static monitoring/troubleshooting page that polls
  ``/data/health`` to display Azure Functions, FastMCP and Azure Tables status.
"""

from __future__ import annotations


def conversations_page() -> str:
    """Return the Conversations SPA HTML.

    The page fetches ``/data/orchestrations`` on load and renders the
    Schema.org Action JSON-LD list as a two-panel UI (sidebar + conversation
    thread).  Selecting an orchestration fetches
    ``/data/orchestrations/{id}`` and renders the nested Conversation +
    Message JSON-LD entirely on the client side.
    """
    return _CONVERSATIONS_HTML


def monitor_page() -> str:
    """Return the static Monitor page HTML.

    The page polls ``/data/health`` every 30 seconds and displays the
    status of Azure Functions, FastMCP, Azure Table Storage, and demo data.
    """
    return _MONITOR_HTML


# ---------------------------------------------------------------------------
# Conversations SPA
# ---------------------------------------------------------------------------

_CONVERSATIONS_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Subconscious — Conversations</title>
  <style>
    /* ── Design tokens ──────────────────────────────────────────────── */
    :root {
      --bg:           #0f1117;
      --surface:      #1a1d27;
      --surface2:     #242836;
      --surface3:     #2d3144;
      --border:       #2e3348;
      --border-h:     #4a4f6a;
      --text:         #e4e6f0;
      --muted:        #8b8fa3;
      --dim:          #5a5e72;
      --accent:       #6c63ff;
      --accent-dim:   rgba(108,99,255,.15);
      --ok:           #22c55e;
      --ok-dim:       rgba(34,197,94,.15);
      --warn:         #f59e0b;
      --warn-dim:     rgba(245,158,11,.15);
      --err:          #ef4444;
      --err-dim:      rgba(239,68,68,.15);
      --radius:       8px;
      --font:         'Segoe UI', system-ui, -apple-system, sans-serif;
      --mono:         'Cascadia Code', 'Fira Code', Consolas, monospace;
    }
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    html, body { height: 100%; overflow: hidden; }
    body { font-family: var(--font); background: var(--bg); color: var(--text); font-size: 14px; }

    /* ── Page skeleton ──────────────────────────────────────────────── */
    .layout { display: grid; grid-template-rows: auto 3px 1fr; height: 100vh; }

    /* ── Top header ─────────────────────────────────────────────────── */
    .header {
      display: flex; align-items: center; gap: 12px;
      padding: 10px 20px;
      background: var(--surface); border-bottom: 1px solid var(--border);
    }
    .header-brand { display: flex; align-items: center; gap: 8px;
                    font-size: .95rem; font-weight: 700; white-space: nowrap; }
    .header-brand .sep { color: var(--dim); font-weight: 400; }
    .header-actions { margin-left: auto; display: flex; align-items: center; gap: 8px; }

    /* ── Progress bar ───────────────────────────────────────────────── */
    #loading-bar { height: 3px; background: transparent; }
    #loading-bar.loading { background: var(--accent);
      animation: bar-slide 1.1s ease-in-out infinite; }
    @keyframes bar-slide {
      0%   { clip-path: inset(0 100% 0 0); }
      50%  { clip-path: inset(0 20% 0 0); }
      100% { clip-path: inset(0 0 0 100%); }
    }

    /* ── Two-column body ────────────────────────────────────────────── */
    .body { display: grid; grid-template-columns: 290px 1fr; overflow: hidden; }

    /* ── Sidebar ────────────────────────────────────────────────────── */
    .sidebar { background: var(--surface); border-right: 1px solid var(--border);
               display: flex; flex-direction: column; overflow: hidden; }
    .sidebar-hdr { padding: 10px 16px; border-bottom: 1px solid var(--border);
                   display: flex; align-items: center; gap: 6px;
                   font-size: .8rem; font-weight: 600; color: var(--muted);
                   text-transform: uppercase; letter-spacing: .06em; }
    #orch-count { margin-left: auto; font-weight: 400; }
    .sidebar-list { flex: 1; overflow-y: auto; }
    .sidebar-list::-webkit-scrollbar { width: 4px; }
    .sidebar-list::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }

    /* ── Orchestration card ─────────────────────────────────────────── */
    .orch-card {
      padding: 12px 16px; border-bottom: 1px solid var(--border);
      cursor: pointer; transition: background .12s;
      border-left: 3px solid transparent;
    }
    .orch-card:hover  { background: var(--surface2); }
    .orch-card:focus  { outline: 2px solid var(--accent); outline-offset: -2px; }
    .orch-card.active { background: var(--accent-dim); border-left-color: var(--accent); }
    .oc-name  { font-size: .88rem; font-weight: 600; line-height: 1.3; margin-bottom: 5px; }
    .oc-meta  { display: flex; align-items: center; gap: 5px; flex-wrap: wrap; }
    .oc-agents { margin-top: 3px; font-size: .71rem; color: var(--dim); }

    /* ── Badge ──────────────────────────────────────────────────────── */
    .badge { display: inline-flex; align-items: center; padding: 2px 7px;
             border-radius: 9999px; font-size: .69rem; font-weight: 600; }
    .b-active    { background: var(--accent-dim); color: var(--accent); }
    .b-completed { background: var(--ok-dim);     color: var(--ok); }
    .b-failed    { background: var(--err-dim);     color: var(--err); }
    .b-muted     { background: var(--surface3);    color: var(--muted); }

    /* ── Main panel ─────────────────────────────────────────────────── */
    .main { display: flex; flex-direction: column; overflow: hidden; }

    .conv-header {
      padding: 14px 22px; border-bottom: 1px solid var(--border);
      background: var(--surface);
    }
    .conv-hdr-top { display: flex; align-items: flex-start;
                    justify-content: space-between; gap: 12px; flex-wrap: wrap; }
    .conv-title   { font-size: 1rem; font-weight: 700; }
    .conv-id      { font-size: .75rem; color: var(--dim); margin-top: 2px;
                    font-family: var(--mono); }
    .conv-meta    { display: flex; align-items: center; gap: 8px; margin-top: 8px;
                    flex-wrap: wrap; font-size: .78rem; color: var(--muted); }
    .conv-meta strong { color: var(--text); }

    /* ── Message thread ─────────────────────────────────────────────── */
    .conv-thread {
      flex: 1; overflow-y: auto; padding: 18px 22px;
      display: flex; flex-direction: column; gap: 14px;
    }
    .conv-thread::-webkit-scrollbar { width: 4px; }
    .conv-thread::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }

    /* ── Message ────────────────────────────────────────────────────── */
    article.msg { display: flex; gap: 10px; max-width: 700px; }
    article.msg.user { flex-direction: row-reverse; align-self: flex-end; }
    article.msg.user .msg-body { align-items: flex-end; }

    .msg-avatar {
      width: 34px; height: 34px; border-radius: 50%;
      background: var(--surface2); border: 1px solid var(--border);
      display: flex; align-items: center; justify-content: center;
      font-size: .72rem; font-weight: 700; flex-shrink: 0; color: var(--accent);
    }
    .msg-body  { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
    .msg-hdr   { display: flex; align-items: center; gap: 6px;
                 font-size: .72rem; color: var(--muted); }
    .msg-hdr strong { color: var(--text); }
    .msg-hdr .seq   { font-family: var(--mono); font-size: .64rem; color: var(--dim); }
    .msg-bubble {
      background: var(--surface); border: 1px solid var(--border);
      border-radius: var(--radius); border-top-left-radius: 2px;
      padding: 10px 13px; line-height: 1.6; font-size: .88rem;
    }
    article.msg.user .msg-bubble {
      background: var(--accent-dim); border-color: var(--accent);
      border-top-right-radius: 2px; border-top-left-radius: var(--radius);
    }
    .msg-note { font-size: .69rem; color: var(--dim); font-style: italic; }

    /* ── JSON-LD footer strip ───────────────────────────────────────── */
    .jsonld-strip {
      padding: 5px 22px; font-family: var(--mono); font-size: .68rem;
      color: var(--dim); background: var(--surface2);
      border-top: 1px solid var(--border);
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }

    /* ── Empty / error state ────────────────────────────────────────── */
    .empty {
      flex: 1; display: flex; flex-direction: column; align-items: center;
      justify-content: center; gap: 10px; padding: 40px; text-align: center;
    }
    .empty .icon { font-size: 2.8rem; opacity: .35; }
    .empty h2    { font-size: 1rem; }
    .empty p     { font-size: .82rem; color: var(--muted); max-width: 300px; }

    /* ── Controls ───────────────────────────────────────────────────── */
    select, button {
      font-family: var(--font); font-size: .8rem; border-radius: var(--radius);
      border: 1px solid var(--border); background: var(--surface2); color: var(--text);
      padding: 5px 10px; cursor: pointer;
      transition: border-color .12s, background .12s;
    }
    select:focus, button:focus { outline: none; border-color: var(--accent); }
    button:hover { background: var(--surface3); border-color: var(--border-h); }
    .btn-icon { padding: 5px 8px; }
    a { color: var(--accent); text-decoration: none; }
    a:hover { text-decoration: underline; }

    /* ── Toast ──────────────────────────────────────────────────────── */
    #toast {
      position: fixed; bottom: 18px; left: 50%; transform: translateX(-50%);
      background: var(--surface3); border: 1px solid var(--border);
      border-radius: var(--radius); padding: 8px 18px;
      font-size: .8rem; opacity: 0; pointer-events: none;
      transition: opacity .25s; z-index: 200;
    }
    #toast.show { opacity: 1; }
  </style>
</head>
<body>
<div class="layout">

  <!-- Header -->
  <header class="header">
    <div class="header-brand">
      <span aria-hidden="true">&#x1f9e0;</span>
      Subconscious
      <span class="sep">/</span>
      <span style="color:var(--muted);font-weight:400">Conversations</span>
    </div>
    <div class="header-actions">
      <select id="status-filter" aria-label="Filter by status">
        <option value="">All statuses</option>
        <option value="active">Active</option>
        <option value="completed">Completed</option>
        <option value="failed">Failed</option>
      </select>
      <button class="btn-icon" id="refresh-btn" title="Refresh" aria-label="Refresh">&#x21bb;</button>
      <a href="/monitor"><button>Monitor</button></a>
      <a href="/"><button>Home</button></a>
    </div>
  </header>

  <!-- Loading bar -->
  <div id="loading-bar" role="progressbar" aria-hidden="true"></div>

  <!-- Two-column body -->
  <div class="body">

    <!-- Sidebar -->
    <aside class="sidebar" aria-label="Orchestration list">
      <div class="sidebar-hdr">
        Orchestrations
        <span id="orch-count">&#x2014;</span>
      </div>
      <div class="sidebar-list" id="sidebar-list" role="list"></div>
    </aside>

    <!-- Main -->
    <main class="main" id="main" role="main">
      <div class="empty" id="placeholder">
        <div class="icon" aria-hidden="true">&#x1f4ac;</div>
        <h2>Select an Orchestration</h2>
        <p>Choose an orchestration from the sidebar to view its full conversation history.</p>
      </div>
    </main>

  </div>
</div>

<div id="toast" role="status" aria-live="polite"></div>

<script>
/* ======================================================================
   Schema.org JSON-LD rendering — pure vanilla JS, no framework
   ====================================================================== */

/* ── Constants ──────────────────────────────────────────────────────── */
const STATUS_URI = {
  'https://schema.org/ActiveActionStatus':    'active',
  'https://schema.org/CompletedActionStatus': 'completed',
  'https://schema.org/FailedActionStatus':    'failed',
};

const INITIALS = {
  ceo:'CE', cfo:'CF', cto:'CT', cmo:'CM',
  coo:'CO', cso:'CS', chro:'CH', cdo:'CD',
};

/* ── Utilities ──────────────────────────────────────────────────────── */
function esc(s) {
  return String(s ?? '')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

function status(action) {
  return action.status || STATUS_URI[action.actionStatus] || 'active';
}

function badge(s) {
  const label = s.charAt(0).toUpperCase() + s.slice(1);
  const cls   = { active:'b-active', completed:'b-completed', failed:'b-failed' }[s] || 'b-muted';
  return `<span class="badge ${cls}">${label}</span>`;
}

function initials(id) {
  const k = (id || '').toLowerCase();
  return INITIALS[k] || k.slice(0,2).toUpperCase() || '??';
}

function fmtDate(iso) {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleString(undefined,
      { month:'short', day:'numeric', hour:'2-digit', minute:'2-digit' });
  } catch { return iso.slice(0,16).replace('T',' '); }
}

/* ── Loading ────────────────────────────────────────────────────────── */
const loadBar = document.getElementById('loading-bar');
const setLoading = on => loadBar.classList.toggle('loading', on);

function toast(msg, ms = 2400) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), ms);
}

/* ── Data fetching ──────────────────────────────────────────────────── */
async function apiFetch(url) {
  const r = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!r.ok) throw new Error(`HTTP ${r.status} — ${url}`);
  return r.json();
}

/* ── Sidebar rendering ──────────────────────────────────────────────── */
let _orchs = [];
let _selId = null;
let _refreshTimer = null;

function renderSidebar(orchs) {
  _orchs = orchs;
  const list  = document.getElementById('sidebar-list');
  const count = document.getElementById('orch-count');
  count.textContent = orchs.length + ' total';

  if (!orchs.length) {
    list.innerHTML = '<div style="padding:24px;text-align:center;color:var(--muted);font-size:.82rem;">No orchestrations found</div>';
    return;
  }

  list.innerHTML = orchs.map(o => {
    const id      = o.orchestration_id || o['@id'] || '';
    const name    = o.purpose || o.name || id;
    const s       = status(o);
    const agents  = (o.agents || []).join(', ') || '&#x2014;';
    const msgs    = o.message_count != null ? `${o.message_count} msg${o.message_count !== 1 ? 's' : ''}` : '';
    const created = fmtDate(o.created_at);
    const sel     = id === _selId ? ' active' : '';

    return `<div class="orch-card${sel}" role="listitem" tabindex="0"
                 data-id="${esc(id)}" aria-label="${esc(name)}, ${s}">
      <div class="oc-name">${esc(name)}</div>
      <div class="oc-meta">
        ${badge(s)}
        ${msgs ? `<span class="badge b-muted">${esc(msgs)}</span>` : ''}
      </div>
      <div class="oc-agents">${esc(agents)}${created ? ' &middot; ' + esc(created) : ''}</div>
    </div>`;
  }).join('');

  list.querySelectorAll('.orch-card').forEach(card => {
    card.addEventListener('click', () => selectOrch(card.dataset.id));
    card.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectOrch(card.dataset.id); }
    });
  });
}

/* ── Conversation rendering ─────────────────────────────────────────── */
function renderConversation(action) {
  const main   = document.getElementById('main');
  const oid    = action.orchestration_id || action['@id'] || '';
  const name   = action.purpose || action.name || oid;
  const s      = status(action);
  const agents = (action.agents || []).join(', ') || '&#x2014;';
  const started = fmtDate(action.created_at || action.startTime);

  /* Schema.org Conversation lives in action.object */
  const conv  = action.object || {};
  /* Support both storage model (messages[]) and JSON-LD demo data (hasPart[]) */
  const msgs  = conv.messages || conv.hasPart || [];
  const total = conv.total != null ? conv.total : msgs.length;

  const hint = `schema:Action &#x2192; ${esc(oid)}  ·  schema:Conversation  ·  ${total} message${total !== 1 ? 's' : ''}`;

  main.innerHTML = `
    <div class="conv-header">
      <div class="conv-hdr-top">
        <div>
          <div class="conv-title">${esc(name)}</div>
          <div class="conv-id">${esc(oid)}</div>
        </div>
        <div style="display:flex;align-items:center;gap:6px;">
          ${badge(s)}
          <button class="btn-icon" data-reload="${esc(oid)}" title="Reload" aria-label="Reload">&#x21bb;</button>
        </div>
      </div>
      <div class="conv-meta">
        <span>Agents: <strong>${esc(agents)}</strong></span>
        ${started ? `<span>Started: <strong>${esc(started)}</strong></span>` : ''}
        <span class="badge b-muted">${total} message${total !== 1 ? 's' : ''}</span>
      </div>
    </div>
    <div class="conv-thread" id="conv-thread" role="log" aria-live="polite" aria-label="Conversation messages">
      ${msgs.length
        ? msgs.map(renderMsg).join('')
        : '<div style="color:var(--muted);text-align:center;padding:40px;">No messages yet</div>'}
    </div>
    <div class="jsonld-strip" title="Schema.org JSON-LD provenance">&#x29e1; ${hint}</div>
  `;
}

/* Render a single Schema.org Message (or storage-model message dict) */
function renderMsg(m) {
  /* Support both storage model keys and JSON-LD keys */
  const agentId = m.agent_id || (m.sender && (m.sender.identifier || m.sender)) || '';
  const role    = m.role || m.additionalType || 'assistant';
  const text    = m.content || m.text || '';
  const ts      = fmtDate(m.created_at || m.dateCreated);
  const note    = m.disambiguatingDescription || '';
  const seqRaw  = m.sequence || m.identifier || m['@id'] || '';
  const seq     = seqRaw.split('/').pop() || seqRaw;
  const isUser  = role === 'user';
  const ini     = initials(agentId);
  const label   = agentId.toUpperCase();

  return `<article class="msg ${isUser ? 'user' : 'assistant'}"
                   role="article" aria-label="Message from ${esc(label)}">
    <div class="msg-avatar" aria-hidden="true" title="${esc(label)}">${esc(ini)}</div>
    <div class="msg-body">
      <div class="msg-hdr">
        <strong>${esc(label)}</strong>
        ${ts ? `<time datetime="${esc(ts)}">${esc(ts)}</time>` : ''}
        ${seq ? `<span class="seq">${esc(seq)}</span>` : ''}
      </div>
      <div class="msg-bubble">${esc(text)}</div>
      ${note ? `<div class="msg-note">${esc(note)}</div>` : ''}
    </div>
  </article>`;
}

/* ── State management ───────────────────────────────────────────────── */
async function selectOrch(id) {
  _selId = id;
  /* Highlight in sidebar */
  document.querySelectorAll('.orch-card').forEach(c =>
    c.classList.toggle('active', c.dataset.id === id));
  /* Update URL */
  const url = new URL(window.location);
  url.searchParams.set('id', id);
  history.pushState({ id }, '', url);
  /* Load conversation */
  await loadConv(id);
  /* Schedule auto-refresh for active orchestrations */
  clearInterval(_refreshTimer);
  const o = _orchs.find(x => (x.orchestration_id || x['@id']) === id);
  if (o && status(o) === 'active') {
    _refreshTimer = setInterval(() => reloadConv(id), 15000);
  }
}

async function loadConv(id) {
  setLoading(true);
  const main = document.getElementById('main');
  main.innerHTML = '<div class="empty"><div class="icon">&#x23f3;</div><p>Loading conversation&#x2026;</p></div>';
  try {
    const data = await apiFetch('/data/orchestrations/' + encodeURIComponent(id));
    renderConversation(data);
    const thread = document.getElementById('conv-thread');
    if (thread) thread.scrollTop = thread.scrollHeight;
  } catch (e) {
    main.innerHTML = `<div class="empty"><div class="icon">&#x26a0;</div><h2>Error</h2><p>${esc(e.message)}</p></div>`;
  } finally { setLoading(false); }
}

async function reloadConv(id) {
  setLoading(true);
  try {
    const data = await apiFetch('/data/orchestrations/' + encodeURIComponent(id));
    renderConversation(data);
    const thread = document.getElementById('conv-thread');
    if (thread) thread.scrollTop = thread.scrollHeight;
  } catch (e) { toast('Reload failed: ' + e.message); }
  finally { setLoading(false); }
}

async function loadOrchestrations() {
  setLoading(true);
  const s = document.getElementById('status-filter').value;
  try {
    const raw  = await apiFetch('/data/orchestrations' + (s ? '?status=' + encodeURIComponent(s) : ''));
    /* Unwrap ItemList wrapper if present */
    const list = Array.isArray(raw) ? raw : (raw.itemListElement || []);
    renderSidebar(list);
    toast('Loaded ' + list.length + ' orchestration' + (list.length !== 1 ? 's' : ''));
  } catch (e) {
    document.getElementById('sidebar-list').innerHTML =
      `<div style="padding:20px;color:var(--err);font-size:.82rem;">&#x26a0; ${esc(e.message)}</div>`;
  } finally { setLoading(false); }
}

/* ── Event wiring ───────────────────────────────────────────────────── */
document.getElementById('refresh-btn').addEventListener('click', loadOrchestrations);
document.getElementById('status-filter').addEventListener('change', loadOrchestrations);
window.addEventListener('popstate', e => { if (e.state?.id) selectOrch(e.state.id); });
/* Delegated handler for the reload button rendered inside conversation panels */
document.getElementById('main').addEventListener('click', e => {
  const btn = e.target.closest('[data-reload]');
  if (btn) reloadConv(btn.dataset.reload);
});

/* ── Boot ───────────────────────────────────────────────────────────── */
(async () => {
  await loadOrchestrations();
  const id = new URLSearchParams(window.location.search).get('id');
  if (id) {
    await selectOrch(id);
  } else if (_orchs.length) {
    await selectOrch(_orchs[0].orchestration_id || _orchs[0]['@id'] || '');
  }
})();
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Monitor page (static, polls /data/health)
# ---------------------------------------------------------------------------

_MONITOR_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Subconscious &#x2014; Monitor</title>
  <style>
    :root {
      --bg:        #0f1117;
      --surface:   #1a1d27;
      --surface2:  #242836;
      --surface3:  #2d3144;
      --border:    #2e3348;
      --text:      #e4e6f0;
      --muted:     #8b8fa3;
      --dim:       #5a5e72;
      --accent:    #6c63ff;
      --ok:        #22c55e;
      --ok-dim:    rgba(34,197,94,.15);
      --warn:      #f59e0b;
      --warn-dim:  rgba(245,158,11,.15);
      --err:       #ef4444;
      --err-dim:   rgba(239,68,68,.15);
      --radius:    8px;
      --font:      'Segoe UI', system-ui, -apple-system, sans-serif;
      --mono:      'Cascadia Code', 'Fira Code', Consolas, monospace;
    }
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: var(--font); background: var(--bg); color: var(--text);
           min-height: 100vh; padding: 28px 20px; }

    .page { max-width: 860px; margin: 0 auto; }

    /* ── Header ─────────────────────────────────────────────────────── */
    header { display: flex; align-items: center; justify-content: space-between;
             margin-bottom: 32px; flex-wrap: wrap; gap: 12px; }
    .brand { display: flex; align-items: center; gap: 10px; }
    .brand h1 { font-size: 1.25rem; font-weight: 700; }
    .brand .sub { color: var(--muted); font-weight: 400; }
    nav { display: flex; gap: 8px; align-items: center;
          font-size: .83rem; color: var(--muted); }
    nav a { color: var(--accent); text-decoration: none; }
    nav a:hover { text-decoration: underline; }

    /* ── Section titles ─────────────────────────────────────────────── */
    h2 { font-size: .78rem; font-weight: 600; text-transform: uppercase;
         letter-spacing: .07em; color: var(--muted); margin: 28px 0 10px; }

    /* ── Status grid ────────────────────────────────────────────────── */
    .status-grid { display: grid;
                   grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
                   gap: 10px; }
    .stat-card { background: var(--surface); border: 1px solid var(--border);
                 border-radius: var(--radius); padding: 14px 18px; }
    .stat-label { font-size: .75rem; color: var(--muted); margin-bottom: 6px; }
    .stat-val   { font-size: 1rem; font-weight: 700; display: flex;
                  align-items: center; gap: 6px; }
    .stat-detail { font-size: .72rem; color: var(--muted); margin-top: 5px;
                   font-family: var(--mono); }

    .s-ok   { color: var(--ok); }
    .s-warn { color: var(--warn); }
    .s-err  { color: var(--err); }
    .s-spin { color: var(--dim); animation: spin 1.2s linear infinite; }
    @keyframes spin { to { opacity: .25; } }
    @keyframes pulse { 0%,100%{opacity:.35} 50%{opacity:1} }
    .s-loading { color: var(--dim); animation: pulse 1.2s ease-in-out infinite; }

    /* ── Quick links ────────────────────────────────────────────────── */
    .links { display: flex; flex-direction: column; gap: 8px; }
    .link-item {
      display: flex; align-items: center; gap: 10px;
      padding: 10px 14px;
      background: var(--surface); border: 1px solid var(--border);
      border-radius: var(--radius);
      text-decoration: none; color: var(--text);
      transition: background .12s, border-color .12s;
    }
    .link-item:hover { background: var(--surface2); border-color: var(--accent); }
    .li-icon { font-size: .95rem; }
    .li-name { font-size: .87rem; font-weight: 600; }
    .li-desc { font-size: .73rem; color: var(--muted); margin-top: 1px; }

    /* ── Info table ─────────────────────────────────────────────────── */
    .card { background: var(--surface); border: 1px solid var(--border);
            border-radius: var(--radius); padding: 4px 18px; }
    table { width: 100%; border-collapse: collapse; font-size: .83rem; }
    tr { border-bottom: 1px solid var(--border); }
    tr:last-child { border-bottom: none; }
    td { padding: 9px 0; vertical-align: top; }
    td:first-child { color: var(--muted); width: 140px; white-space: nowrap; }
    code { font-family: var(--mono); font-size: .79rem; color: var(--accent); }

    /* ── Footer ─────────────────────────────────────────────────────── */
    footer { margin-top: 36px; padding-top: 16px; border-top: 1px solid var(--border);
             font-size: .72rem; color: var(--dim); }
    footer a { color: var(--accent); text-decoration: none; }
    footer a:hover { text-decoration: underline; }

    /* ── Refresh badge ──────────────────────────────────────────────── */
    #refresh-time { font-size: .72rem; color: var(--dim); }
  </style>
</head>
<body>
<div class="page">

  <header>
    <div class="brand">
      <span aria-hidden="true">&#x1f9e0;</span>
      <h1>Subconscious <span class="sub">Monitor</span></h1>
    </div>
    <nav>
      <span id="refresh-time"></span>
      &nbsp;&middot;&nbsp;
      <a href="/view/conversations">Conversations</a>
      &nbsp;&middot;&nbsp;
      <a href="/">Home</a>
    </nav>
  </header>

  <!-- Status cards -->
  <h2>System Health</h2>
  <div class="status-grid">
    <div class="stat-card">
      <div class="stat-label">Azure Functions</div>
      <div class="stat-val s-loading" id="s-funcs">&#x23f3; Checking</div>
      <div class="stat-detail" id="d-funcs"></div>
    </div>
    <div class="stat-card">
      <div class="stat-label">FastMCP Endpoint</div>
      <div class="stat-val s-loading" id="s-mcp">&#x23f3; Checking</div>
      <div class="stat-detail" id="d-mcp">/mcp</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Azure Table Storage</div>
      <div class="stat-val s-loading" id="s-storage">&#x23f3; Checking</div>
      <div class="stat-detail" id="d-storage"></div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Demo Data</div>
      <div class="stat-val s-loading" id="s-demo">&#x23f3; Checking</div>
      <div class="stat-detail" id="d-demo"></div>
    </div>
  </div>

  <!-- Quick links -->
  <h2>Quick Links</h2>
  <div class="links">
    <a href="/view/conversations" class="link-item">
      <span class="li-icon" aria-hidden="true">&#x1f4ac;</span>
      <div>
        <div class="li-name">Conversations Browser</div>
        <div class="li-desc">Browse multi-agent orchestration conversations</div>
      </div>
    </a>
    <a href="/mcp" class="link-item">
      <span class="li-icon" aria-hidden="true">&#x26a1;</span>
      <div>
        <div class="li-name">MCP Endpoint</div>
        <div class="li-desc">Connect your MCP client (Claude Desktop, Copilot) here</div>
      </div>
    </a>
    <a href="/data/orchestrations" class="link-item" target="_blank" rel="noopener">
      <span class="li-icon" aria-hidden="true">&#x29e1;</span>
      <div>
        <div class="li-name">Orchestrations JSON-LD</div>
        <div class="li-desc">Raw Schema.org Action JSON-LD data feed</div>
      </div>
    </a>
    <a href="/data/health" class="link-item" target="_blank" rel="noopener">
      <span class="li-icon" aria-hidden="true">&#x2764;</span>
      <div>
        <div class="li-name">Health JSON</div>
        <div class="li-desc">Raw health status JSON</div>
      </div>
    </a>
  </div>

  <!-- Endpoint reference -->
  <h2>Endpoint Reference</h2>
  <div class="card">
    <table aria-label="Endpoint reference">
      <tr><td>MCP</td><td><code>POST /mcp/{*rest}</code> &#x2014; FastMCP protocol (tools, resources, prompts)</td></tr>
      <tr><td>Conversations</td><td><code>GET /view/conversations</code> &#x2014; HTML5/CSS3 conversation browser</td></tr>
      <tr><td>Monitor</td><td><code>GET /monitor</code> &#x2014; This page</td></tr>
      <tr><td>Data</td><td><code>GET /data/orchestrations</code> &#x2014; Schema.org ItemList JSON-LD</td></tr>
      <tr><td>Data</td><td><code>GET /data/orchestrations/{id}</code> &#x2014; Schema.org Action + Conversation JSON-LD</td></tr>
      <tr><td>Health</td><td><code>GET /data/health</code> &#x2014; Health status JSON</td></tr>
    </table>
  </div>

  <!-- MCP tools reference -->
  <h2>MCP Tools &amp; Resources</h2>
  <div class="card">
    <table aria-label="MCP tools reference">
      <tr><td>App</td><td><code>show_conversations</code>, <code>fetch_orchestrations</code>, <code>fetch_conversation</code></td></tr>
      <tr><td>Orchestrations</td><td><code>create_orchestration</code>, <code>list_orchestrations</code>, <code>complete_orchestration</code></td></tr>
      <tr><td>Messages</td><td><code>persist_message</code>, <code>persist_conversation_turn</code>, <code>get_conversation</code></td></tr>
      <tr><td>Schemas</td><td><code>list_schemas</code>, <code>get_schema</code>, <code>store_schema_context</code>, <code>get_schema_context</code>, <code>list_schema_contexts</code></td></tr>
      <tr><td>Resources</td><td><code>orchestration://&lt;id&gt;</code> &nbsp; <code>schema://&lt;name&gt;</code> &nbsp; <code>schema-context://&lt;name&gt;/&lt;id&gt;</code></td></tr>
      <tr><td>Prompts</td><td><code>summarize_conversation</code></td></tr>
    </table>
  </div>

  <footer>
    &#x1f9e0; Subconscious MCP Server &middot; FastMCP on Azure Functions &middot;
    Schema.org JSON-LD &middot; <a href="https://github.com/ASISaga/subconscious.asisaga.com" rel="noopener">GitHub</a>
  </footer>

</div>

<script>
/* ── Health check ───────────────────────────────────────────────────── */
async function checkHealth() {
  try {
    const r    = await fetch('/data/health', { headers: { Accept: 'application/json' } });
    const data = await r.json();

    set('s-funcs',   '&#x2705; Running',  's-ok');
    set('d-funcs',   data.version || 'Azure Functions v4');

    set('s-mcp',     '&#x2705; Online',   's-ok');
    set('d-mcp',     '/mcp &middot; ' + (data.tool_count || '14+') + ' tools');

    if (data.storage === 'demo') {
      set('s-storage', '&#x26a0; Demo mode', 's-warn');
      set('d-storage', 'No Azure Storage connection configured');
    } else if (data.storage === 'ok') {
      set('s-storage', '&#x2705; Connected', 's-ok');
      set('d-storage', 'Azure Table Storage');
    } else {
      set('s-storage', '&#x274c; Error', 's-err');
      set('d-storage', data.storage_error || 'Unknown error');
    }

    if (data.demo_conversations != null) {
      set('s-demo', '&#x2705; ' + data.demo_conversations + ' conversations', 's-ok');
      set('d-demo', data.demo_data_dir || 'data/conversations/');
    } else {
      set('s-demo', '&#x2014; Not active', '');
      set('d-demo', 'Azure Storage is in use');
    }

    document.getElementById('refresh-time').textContent =
      'Last refresh: ' + new Date().toLocaleTimeString();

  } catch (e) {
    set('s-funcs', '&#x274c; Unreachable', 's-err');
    ['mcp','storage','demo'].forEach(k => set('s-' + k, '&#x2014; Unknown', ''));
  }
}

function set(id, html, cls) {
  const el = document.getElementById(id);
  if (!el) return;
  el.innerHTML = html;
  el.className = el.className.replace(/\\bs-\\S+/g, '').trim();
  if (cls) el.classList.add(cls);
}

checkHealth();
setInterval(checkHealth, 30000);
</script>
</body>
</html>
"""
