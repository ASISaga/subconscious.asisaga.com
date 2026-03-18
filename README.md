# Subconscious — Multi-Agent Conversation Persistence MCP Server

An **Azure Functions**-hosted [Model Context Protocol](https://modelcontextprotocol.io) server that enables **Microsoft Agent Framework** orchestrations (deployed on **Foundry Agent Service**) to persist and retrieve multi-agent conversations.

## Features

| Capability | Description |
|---|---|
| **Streamable HTTP** | MCP endpoint at `/mcp` using FastMCP streamable-HTTP transport |
| **MCP Apps UI** | Built-in web interface at `/` for browsing orchestrations and conversations |
| **Conversation Persistence** | Azure Table Storage–backed storage for multi-agent conversation history |
| **Orchestration Management** | Create, list, complete, and query orchestrations |
| **REST API** | Lightweight JSON API at `/api/*` powering the UI |
| **On-Demand Retrieval** | Any authenticated MCP client can retrieve conversations by orchestration ID |

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

### Endpoints

| Path | Description |
|---|---|
| `/` | MCP Apps UI — browse orchestrations and conversations |
| `/mcp` | MCP streamable-HTTP endpoint |
| `/api/health` | Health check |
| `/api/orchestrations` | List orchestrations |
| `/api/orchestrations/{id}` | Get orchestration details |
| `/api/orchestrations/{id}/messages` | Get conversation messages |

## MCP Tools

| Tool | Description |
|---|---|
| `create_orchestration` | Register a new orchestration |
| `persist_message` | Append a single message to a conversation |
| `persist_conversation_turn` | Persist multiple messages in one call |
| `get_conversation` | Retrieve full conversation by orchestration ID |
| `list_orchestrations` | List all orchestrations (with optional status filter) |
| `complete_orchestration` | Mark an orchestration as completed |

## MCP Resources

| URI | Description |
|---|---|
| `orchestration://{id}` | Full orchestration metadata + conversation history |

## MCP Prompts

| Prompt | Description |
|---|---|
| `summarize_conversation` | Generate a summarisation prompt for an orchestration |

## Architecture

```
┌──────────────────────────────────────────────┐
│            Azure Functions (ASGI)             │
│  ┌──────────┬───────────┬──────────────────┐  │
│  │ /mcp     │ /api/*    │ /  (UI)          │  │
│  │ FastMCP  │ REST API  │ MCP Apps UI      │  │
│  └────┬─────┴─────┬─────┴────────┬─────────┘  │
│       └───────────┼──────────────┘             │
│              ┌────▼────┐                       │
│              │ storage │                       │
│              └────┬────┘                       │
│         ┌─────────▼─────────┐                  │
│         │ Azure Table Store │                  │
│         │  • Orchestrations │                  │
│         │  • Conversations  │                  │
│         └───────────────────┘                  │
└──────────────────────────────────────────────┘
```

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