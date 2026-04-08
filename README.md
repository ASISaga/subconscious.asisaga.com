# Subconscious — Multi-Agent Conversation & Schema Context Persistence MCP Server

An **Azure Functions**-hosted [Model Context Protocol](https://modelcontextprotocol.io) server that enables **Microsoft Agent Framework** orchestrations (deployed on **Foundry Agent Service**) to:

1. **Persist and retrieve multi-agent conversations** — every message from every agent in an orchestration is stored durably and can be recalled by orchestration ID.
2. **Serve boardroom mind schemas** — the seven JSON Schema definitions from `boardroom/mind/schemas/` are exposed as MCP Resources and Tools so agents can inspect and validate their own mind documents.
3. **Persist and retrieve schema contexts** — JSON-LD documents that conform to a mind schema (Manas, Buddhi, Ahankara, Chitta, and entity perspectives) are stored in Azure Table Storage and can be retrieved by `(schema_name, context_id)` key.

This is the local copy of [ASISaga/subconscious.asisaga.com](https://github.com/ASISaga/subconscious.asisaga.com), extended with native schema context support.

---

## Features

| Capability | Description |
|---|---|
| **Streamable HTTP** | MCP endpoint at `/mcp` using FastMCP streamable-HTTP transport |
| **MCP Apps UI** | Built-in web interface at `/` for browsing orchestrations and conversations |
| **Conversation Persistence** | Azure Table Storage–backed storage for multi-agent conversation history |
| **Orchestration Management** | Create, list, complete, and query orchestrations |
| **Schema Definitions** | Serve the 7 boardroom mind schemas as MCP Resources and Tools |
| **Schema Context Persistence** | Store and retrieve JSON-LD mind documents (Manas, Buddhi, Ahankara, Chitta, entity perspectives) |
| **REST API** | Lightweight JSON API at `/api/*` powering the UI and schema endpoints |

---

## Quick Start

### Prerequisites

- Python 3.11+
- [Azure Functions Core Tools](https://learn.microsoft.com/azure/azure-functions/functions-run-local)
- Azure Storage account (or [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite) for local dev)

### Local Development

```bash
# Install dependencies
pip install -e ".[dev]"

# Configure local storage (edit local.settings.json)
# Start Azurite for local Table Storage emulation

# Run the Azure Function locally
func start
```

---

## Endpoints

| Path | Description |
|---|---|
| `/` | MCP Apps UI — browse orchestrations and conversations |
| `/mcp` | MCP streamable-HTTP endpoint |
| `/api/health` | Health check |
| `/api/orchestrations` | List orchestrations |
| `/api/orchestrations/{id}` | Get orchestration details |
| `/api/orchestrations/{id}/messages` | Get conversation messages |
| `/api/schemas` | List all boardroom mind schemas |
| `/api/schemas/{name}` | Get a schema definition by name |
| `/api/schema-contexts` | List stored schema contexts |
| `/api/schema-contexts/{schema}/{id}` | Get or store a schema context |

---

## MCP Tools

### Conversation

| Tool | Description |
|---|---|
| `create_orchestration` | Register a new orchestration |
| `persist_message` | Append a single message to a conversation |
| `persist_conversation_turn` | Persist multiple messages in one call |
| `get_conversation` | Retrieve full conversation by orchestration ID |
| `list_orchestrations` | List all orchestrations (with optional status filter) |
| `complete_orchestration` | Mark an orchestration as completed |

### Schema Definitions (read-only)

| Tool | Description |
|---|---|
| `list_schemas` | List all available boardroom mind schemas |
| `get_schema` | Retrieve a schema definition by name |

### Schema Context Persistence

| Tool | Description |
|---|---|
| `store_schema_context` | Persist a JSON-LD document conforming to a mind schema |
| `get_schema_context` | Retrieve a stored schema context by schema name and context id |
| `list_schema_contexts` | List stored schema contexts (optionally filtered by schema name) |

---

## MCP Resources

| URI | Description |
|---|---|
| `orchestration://{id}` | Full orchestration metadata + conversation history |
| `schema://{name}` | Boardroom mind schema definition (JSON Schema) |
| `schema-context://{schema}/{id}` | Stored schema context document (JSON-LD) |

Available schema names: `manas`, `buddhi`, `ahankara`, `chitta`, `action-plan`, `entity-context`, `entity-content`.

---

## MCP Prompts

| Prompt | Description |
|---|---|
| `summarize_conversation` | Generate a summarisation prompt for an orchestration |

---

## Schema Context Usage

Agents use `store_schema_context` to persist their mind-layer documents between sessions:

```python
# An agent stores its Manas (memory state)
await mcp.call_tool("store_schema_context", {
    "schema_name": "manas",
    "context_id": "ceo",
    "data": {
        "@context": "https://asisaga.com/contexts/agent.jsonld",
        "@id": "agent:ceo",
        "@type": "CEOAgent",
        "schema_version": "2.0.0",
        ...
    }
})

# Later, retrieve it
result = await mcp.call_tool("get_schema_context", {
    "schema_name": "manas",
    "context_id": "ceo",
})
# result["data"] contains the full JSON-LD document

# Entity perspective contexts use compound keys
await mcp.call_tool("store_schema_context", {
    "schema_name": "entity-context",
    "context_id": "ceo/company",
    "data": { ... }
})
```

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│               Azure Functions (ASGI)                      │
│  ┌──────────┬───────────┬──────────────────────────────┐  │
│  │ /mcp     │ /api/*    │ /  (UI)                      │  │
│  │ FastMCP  │ REST API  │ MCP Apps UI                  │  │
│  └────┬─────┴─────┬─────┴────────────────┬─────────────┘  │
│       └───────────┼─────────────────────┘                 │
│           ┌───────┴──────────┐                            │
│           │   storage.py     │  schema_storage.py         │
│           │  (conversations)  │  (schemas + contexts)      │
│           └───────┬──────────┘──────────────┬────────────  │
│          ┌────────▼──────────────────────────▼────────┐   │
│          │          Azure Table Storage               │   │
│          │  • Orchestrations   • Conversations        │   │
│          │  • SchemaContexts                          │   │
│          └────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
```

### Storage Tables

| Table | PartitionKey | RowKey | Content |
|---|---|---|---|
| `Orchestrations` | `"orchestrations"` | orchestration_id | Purpose, Status, Agents, MessageCount |
| `Conversations` | orchestration_id | `msg_<epoch_us>_<rand>` | AgentId, Role, Content, Metadata |
| `SchemaContexts` | schema_name | context_id | JSON-LD document (Content), UpdatedAt |

---

## Boardroom Mind Schemas

The server exposes the 7 JSON Schema definitions from `boardroom/mind/schemas/`:

| Schema Name | File | Description |
|---|---|---|
| `manas` | `manas.schema.json` | Agent memory state — context and content layers |
| `buddhi` | `buddhi.schema.json` | Agent intellect — legend-derived domain wisdom |
| `ahankara` | `ahankara.schema.json` | Agent identity — ego that constrains the intellect |
| `chitta` | `chitta.schema.json` | Pure intelligence — mind without memory |
| `action-plan` | `action-plan.schema.json` | Agent action plan — steps toward company purpose |
| `entity-context` | `entity-context.schema.json` | Immutable entity perspective (context layer) |
| `entity-content` | `entity-content.schema.json` | Mutable entity perspective (content layer) |

The schema files are resolved from the `boardroom/mind/schemas/` directory relative to the repository root (configurable via the `SCHEMAS_DIR` environment variable).

---

## Testing

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## Deployment

```bash
# Using Azure Developer CLI
azd up
```
