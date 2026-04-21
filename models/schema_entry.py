"""SchemaEntry — metadata record for a registered mind schema."""

from __future__ import annotations

from pydantic import BaseModel


class SchemaEntry(BaseModel):
    """Metadata record for a registered mind schema."""

    name: str
    filename: str
    available: bool
    title: str = ""
    description: str = ""
