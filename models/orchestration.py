"""Orchestration — summary record for an orchestration."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class Orchestration(BaseModel):
    """Summary record for an orchestration."""

    orchestration_id: str
    purpose: str = ""
    status: str = "active"
    agents: list[str] = Field(default_factory=list)
    message_count: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
