"""MCP prompts — conversation summarisation prompt."""

from __future__ import annotations

from server import mcp
from storage import conversations as storage_conv


@mcp.prompt()
def summarize_conversation(orchestration_id: str) -> str:
    """Generate a prompt that asks the model to summarise an orchestration conversation."""
    messages = storage_conv.get_conversation(orchestration_id, limit=500)
    if not messages:
        return f"No messages found for orchestration '{orchestration_id}'."

    lines = [f"Summarise the following multi-agent conversation (orchestration {orchestration_id}):\n"]
    for msg in messages:
        lines.append(f"[{msg['role']}] {msg['agent_id']}: {msg['content']}")
    lines.append("\nProvide a concise summary covering key decisions, actions taken, and outcomes.")
    return "\n".join(lines)
