"""Message — a persisted conversation message with server-assigned fields."""

from __future__ import annotations

from models.message_input import MessageInput


class Message(MessageInput):
    """A persisted conversation message with server-assigned fields."""

    orchestration_id: str
    sequence: str
    created_at: str
