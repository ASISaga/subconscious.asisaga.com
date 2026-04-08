"""Pydantic models for orchestration, conversation, and schema context data."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class MessageInput(BaseModel):
    """A single message to persist in a conversation turn."""

    agent_id: str = Field(..., description="Identifier of the agent that produced the message.")
    role: str = Field(..., description="Message role: user | assistant | system | tool.")
    content: str = Field(..., description="Full text content of the message.")
    metadata: dict[str, Any] | None = Field(default=None, description="Optional structured metadata.")


class Message(MessageInput):
    """A persisted conversation message with server-assigned fields."""

    orchestration_id: str
    sequence: str
    created_at: str


class Orchestration(BaseModel):
    """Summary record for an orchestration."""

    orchestration_id: str
    purpose: str = ""
    status: str = "active"
    agents: list[str] = Field(default_factory=list)
    message_count: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class ConversationPage(BaseModel):
    """Paginated conversation response."""

    orchestration_id: str
    messages: list[Message]
    total: int
    has_more: bool = False


class SchemaEntry(BaseModel):
    """Metadata record for a registered mind schema."""

    name: str
    filename: str
    available: bool
    title: str = ""
    description: str = ""


class SchemaContextRecord(BaseModel):
    """Summary record for a stored schema context."""

    schema_name: str
    context_id: str
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
