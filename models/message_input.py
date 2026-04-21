"""MessageInput — a single message to persist in a conversation turn."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MessageInput(BaseModel):
    """A single message to persist in a conversation turn."""

    agent_id: str = Field(..., description="Identifier of the agent that produced the message.")
    role: str = Field(..., description="Message role: user | assistant | system | tool.")
    content: str = Field(..., description="Full text content of the message.")
    metadata: dict[str, Any] | None = Field(default=None, description="Optional structured metadata.")
