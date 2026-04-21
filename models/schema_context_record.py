"""SchemaContextRecord — summary record for a stored schema context."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class SchemaContextRecord(BaseModel):
    """Summary record for a stored schema context."""

    schema_name: str
    context_id: str
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
