"""FastMCP server — Layer 3: The Persistent Subconscious.

Exposes BoardroomMemory state as an MCP Resource and strategic actions as MCP Tools,
compatible with Model Context Protocol v1.0 for remote connection.
"""

from __future__ import annotations

import logging
from typing import Any

from fastmcp import FastMCP

from subconscious.deploy import execute_bicep_deployment
from subconscious.storage import get_boardroom_state, record_event

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "Subconscious",
    instructions=(
        "The Persistent Subconscious: Single Source of Truth for the ASI Boardroom. "
        "Stores every debate, resonance score, and decision in Azure Table Storage. "
        "Exposes memories as Resources and business actions as Tools."
    ),
)


@mcp.resource("infinity://boardroom/state")
def boardroom_state() -> dict[str, Any]:
    """Return the latest Resonance Score and current North Star goal."""
    return get_boardroom_state()


@mcp.tool()
def record_strategic_event(
    agent_id: str,
    event_type: str,
    content: str,
    resonance_score: float,
) -> dict[str, Any]:
    """Record a strategic event to BoardroomMemory with an inverted timestamp RowKey.

    Args:
        agent_id: Identifier of the agent that generated the event.
        event_type: Category of the event (e.g. ``debate``, ``decision``, ``insight``).
        content: Full text content of the event.
        resonance_score: Numeric resonance score (0.0–1.0) assigned to this event.

    Returns:
        A dict with the generated ``row_key``, ``status``, and ``timestamp``.
    """
    return record_event(agent_id, event_type, content, resonance_score)


@mcp.tool()
def execute_bicep_deploy(
    bicep_file: str,
    resource_group: str,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Deploy an Azure Bicep template using the Azure Python SDK.

    Args:
        bicep_file: Repository-relative path to the ``.bicep`` file
            (e.g. ``infra/main.bicep``).
        resource_group: Target Azure resource group name.
        parameters: Optional ARM template parameter values as a plain dict
            (keys are parameter names, values are the parameter values).

    Returns:
        A dict with deployment ``name``, ``resource_group``, ``bicep_file``,
        and ``status`` (``"started"``).
    """
    return execute_bicep_deployment(bicep_file, resource_group, parameters)
