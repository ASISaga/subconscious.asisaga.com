"""ConversationPage — paginated conversation response."""

from __future__ import annotations

from pydantic import BaseModel

from models.message import Message


class ConversationPage(BaseModel):
    """Paginated conversation response."""

    orchestration_id: str
    messages: list[Message]
    total: int
    has_more: bool = False
