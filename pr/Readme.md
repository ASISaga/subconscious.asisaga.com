# subconscious.asisaga.com — MCP Persistence for Business Infinity Boardroom

## Objective

Act as the persistence layer for all Business Infinity boardroom interactions,
exposing MCP tools that the Agent Operating System (AOS) calls to store and
retrieve text messages, MCP app payloads (graphical UI elements), session
state, and agent context for both structured workflows and dynamic CXO
discussions.

## Context

`subconscious.asisaga.com` is the storage backend in the Business Infinity
architecture.  It is never called directly by the frontend; the Agent
Operating System calls its MCP tools on behalf of every boardroom session.

The boardroom operates in two modes, both requiring full conversation
persistence:

1. **Structured workflows** — Step-by-step conversations between a
   workflow-owner agent and an external entity.  Includes text messages,
   MCP app payloads (`boardroom_ui` with narrative, response, actions, and
   navigation), and step state.
2. **Dynamic discussions** — Free-form debates between CXO agents.
   Includes text messages, MCP app payloads (dashboards, charts), resonance
   scores, and debate context.

All conversations must be replayable on page refresh or session reconnect so
that the `<chatroom>` component can restore every message and graphical
element in the correct order.

---

## Requirements

### 1. MCP Server — Tool Definitions

`subconscious.asisaga.com` exposes the following MCP tools.  The AOS calls
these tools whenever it needs to store or retrieve conversation data.

#### 1.1 `persist_message`

Store a single text message from any boardroom session.

**Input schema**:

```json
{
  "session_id":   "string  — unique session identifier",
  "sender":       "string  — agent_id or 'user'",
  "role":         "string  — 'agent' | 'user' | 'system'",
  "content":      "string  — message text",
  "timestamp":    "string  — ISO 8601 UTC",
  "mode":         "string  — 'structured' | 'dynamic'",
  "workflow_id":  "string? — present for structured sessions",
  "step_id":      "string? — present for structured sessions"
}
```

**Response**:

```json
{ "entry_id": "string — unique ID for this stored entry" }
```

#### 1.2 `persist_mcp_app`

Store a complete MCP app payload alongside any associated text message.
Payloads are stored as structured JSON and never flattened to text.

**Input schema**:

```json
{
  "session_id":  "string  — unique session identifier",
  "sender":      "string  — agent_id that produced the payload",
  "app_id":      "string  — e.g. 'boardroom_ui'",
  "payload":     "object  — full MCP app payload (see §4)",
  "timestamp":   "string  — ISO 8601 UTC",
  "mode":        "string  — 'structured' | 'dynamic'",
  "workflow_id": "string? — present for structured sessions",
  "step_id":     "string? — present for structured sessions"
}
```

**Response**:

```json
{ "entry_id": "string — unique ID for this stored entry" }
```

#### 1.3 `set_session_state`

Create or update the state record for a session.  Called by AOS when a
session starts, a step changes, or a workflow completes.

**Input schema**:

```json
{
  "session_id":  "string  — unique session identifier",
  "mode":        "string  — 'structured' | 'dynamic'",
  "workflow_id": "string? — active workflow (structured mode only)",
  "step_id":     "string? — current step ID (structured mode only)",
  "owner":       "string? — owner agent_id (structured mode only)",
  "agents":      ["string"] ,
  "status":      "string  — 'active' | 'completed' | 'paused'",
  "updated_at":  "string  — ISO 8601 UTC"
}
```

**Response**:

```json
{ "session_id": "string", "updated_at": "string" }
```

#### 1.4 `get_session_state`

Retrieve the current state for a session.  Called by AOS when a client
reconnects.

**Input schema**:

```json
{ "session_id": "string" }
```

**Response**:

```json
{
  "session_id":  "string",
  "mode":        "string",
  "workflow_id": "string?",
  "step_id":     "string?",
  "owner":       "string?",
  "agents":      ["string"],
  "status":      "string",
  "created_at":  "string",
  "updated_at":  "string"
}
```

#### 1.5 `get_conversation`

Return the full ordered conversation for a session, including both text
messages and MCP app payloads.  Used for conversation replay on reconnect.

**Input schema**:

```json
{
  "session_id": "string",
  "since":      "string? — ISO 8601 UTC; return entries after this timestamp"
}
```

**Response**:

```json
{
  "session_id": "string",
  "entries": [
    {
      "entry_id":   "string",
      "type":       "string — 'message' | 'mcp_app'",
      "sender":     "string",
      "role":       "string — 'agent' | 'user' | 'system'",
      "timestamp":  "string",
      "mode":       "string",
      "workflow_id":"string?",
      "step_id":    "string?",
      "content":    "string? — present for type='message'",
      "app_id":     "string? — present for type='mcp_app'",
      "payload":    "object? — present for type='mcp_app'"
    }
  ]
}
```

Entries are sorted by `timestamp` ascending.  The `<chatroom>` component
replays these in order to restore the full visual state.

---

### 2. MCP App Payload Storage Schema

MCP app payloads are stored verbatim as structured JSON objects using the
envelope defined in `docs/workflow/Communication.md`.

#### 2.1 `boardroom_ui` Payload (structured workflow)

```json
{
  "app_id": "boardroom_ui",
  "payload": {
    "narrative":   "string — step narrative text",
    "response":    "string — agent response text",
    "actions": [
      {
        "label":       "string — button text",
        "description": "string — contextual info above the button",
        "url":         "string — target URL"
      }
    ],
    "navigation": {
      "next": "string? — next step_id",
      "back": "string? — previous step_id"
    }
  }
}
```

#### 2.2 Dynamic Discussion MCP App Payload

Dynamic CXO discussions may produce additional `app_id` payloads (charts,
dashboards, resonance visualisations) that are stored using the same
`persist_mcp_app` tool:

```json
{
  "app_id": "boardroom_resonance",
  "payload": {
    "topic":        "string — debate topic",
    "agents":       ["string — agent_ids participating"],
    "proposals": [
      {
        "agent_id":        "string",
        "proposal":        "string — proposed action",
        "resonance_score": "number — 0.0–1.0 alignment with company purpose"
      }
    ],
    "winner":       "string? — agent_id of highest-resonance proposal",
    "action_taken": "string? — the executed action"
  }
}
```

Future `app_id` types (e.g. `boardroom_chart`, `boardroom_form`) must be
stored without modification, ensuring forward compatibility as the platform
evolves.

---

### 3. Session State Persistence

Every boardroom session has a state record that captures the current mode
and position within that session.

#### 3.1 Structured Workflow State

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | Unique session identifier |
| `mode` | `"structured"` | Session type |
| `workflow_id` | string | Active workflow (e.g. `pitch_business_infinity`) |
| `step_id` | string | Current step ID within the workflow |
| `owner` | string | Agent conducting the workflow (e.g. `founder`) |
| `agents` | string[] | `[owner]` for structured mode |
| `status` | string | `active` \| `completed` \| `paused` |
| `created_at` | ISO 8601 | Session start time |
| `updated_at` | ISO 8601 | Last state change time |

#### 3.2 Dynamic Discussion State

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | Unique session identifier |
| `mode` | `"dynamic"` | Session type |
| `workflow_id` | null | Not applicable for dynamic mode |
| `step_id` | null | Not applicable for dynamic mode |
| `owner` | null | All CXOs participate equally |
| `agents` | string[] | All participating CXO agent IDs |
| `status` | string | `active` \| `completed` \| `paused` |
| `created_at` | ISO 8601 | Session start time |
| `updated_at` | ISO 8601 | Last state change time |

---

### 4. Multi-Workflow Session Support

Support concurrent sessions for every registered workflow type.  Any number
of sessions may be active simultaneously across different users and workflows.

| Workflow ID | Owner | Mode |
|-------------|-------|------|
| `pitch_business_infinity` | `founder` | structured |
| `marketing_business_infinity` | `cmo` | structured |
| `onboard_new_business` | `coo` | structured |
| `crisis_response` | `ceo` | structured |
| `quarterly_strategic_review` | `ceo` | structured |
| `product_launch` | `ceo` | structured |
| *(none)* | *(all CXOs)* | dynamic |

Session records are independent per `session_id`.  The same user may have
multiple active sessions (e.g. one pitch session and one marketing session)
at the same time.

---

### 5. Dynamic Discussion Persistence

Dynamic CXO discussions require additional data beyond simple message
storage:

- **Resonance scores** — Each proposal carries a `resonance_score` (0.0–1.0)
  representing alignment with the company's purpose.  Scores are stored
  inside the `boardroom_resonance` MCP app payload (§2.2).
- **Debate context** — The full list of CXO agent IDs participating, the
  debate topic, and the outcome (winner agent and action taken) are stored
  as part of the MCP app payload.
- **Thread ordering** — Agent-to-agent messages are ordered by timestamp to
  enable replay of the debate sequence.

---

### 6. Session State REST API

In addition to MCP tools, expose REST endpoints so that AOS and diagnostic
tooling can access session state directly.

```
GET  /sessions/{session_id}/state
     → SessionState (§3)

PUT  /sessions/{session_id}/state
     Body: { workflow_id?, step_id?, owner?, agents?, status? }
     → Updated SessionState

GET  /sessions/{session_id}/conversation
     Query: ?since=<ISO 8601>   (optional)
     → ConversationReplay (§1.5 response format)

GET  /sessions/{session_id}/conversation/mcp_apps
     Query: ?app_id=<app_id>    (optional filter)
     → All MCP app payload entries for the session

DELETE /sessions/{session_id}
     → Purge all data for the session (admin use only)
```

All endpoints require an `Authorization: Bearer <token>` header containing
a valid AOS service-to-service token.

---

### 7. Conversation Replay on Reconnect

When a client reconnects or the page is refreshed, AOS calls
`get_conversation` with the `session_id`.  The response must:

- Return **all** entries (text and MCP app payloads) in chronological order.
- Include sufficient metadata (`sender`, `role`, `type`, `workflow_id`,
  `step_id`, `timestamp`) for the `<chatroom>` component to render each
  entry correctly without additional API calls.
- Support incremental replay via the `since` parameter for long-running
  sessions that have accumulated many entries.
- Replay must be idempotent — calling `get_conversation` multiple times
  for the same `session_id` must return identical results (no side effects).

---

### 8. Storage Architecture

All data is partitioned by `session_id` for efficient retrieval.

| Collection / Table | Primary Key | Description |
|--------------------|-------------|-------------|
| `sessions` | `session_id` | One record per session; holds mode and current state |
| `conversation_entries` | `(session_id, entry_id)` | All text and MCP app entries, ordered by `timestamp` |

The `conversation_entries` table stores both `type='message'` and
`type='mcp_app'` rows in the same collection to preserve the interleaved
order of text and graphical elements.

---

### 9. Authentication

- All MCP tool calls from AOS must include the AOS service-to-service API
  key in the MCP request metadata.
- All REST API calls must include an `Authorization: Bearer <token>` header.
- No direct client access is permitted — `subconscious.asisaga.com` is an
  internal service called only by AOS.

---

## Dependencies

- `agent-operating-system` — The sole caller of MCP tools; provides session
  IDs and manages the transport layer between clients and subconscious
- `business-infinity` — Workflow definitions (`WORKFLOW_REGISTRY`) and
  `workflow_id` / `step_id` values used in session state records

## References

→ **Communication protocol**: `docs/workflow/Communication.md`
→ **Architecture**: `docs/workflow/Architecture.md`
→ **Workflow YAML samples**: `docs/workflow/samples/`
→ **Boardroom schema**: `docs/workflow/boardroom.yaml`
→ **Multi-repo roadmap**: `docs/multi-repository-implementation.md`
→ **AOS PR spec**: `docs/workflow/pr/agent-operating-system/Readme.md`
→ **SDK PR spec**: `docs/workflow/pr/aos-client-sdk/Readme.md`