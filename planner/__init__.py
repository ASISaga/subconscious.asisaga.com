"""Microsoft Planner integration for CXO task and responsibility planning.

Provides tools for syncing CXO integrity tasks and responsibilities to
Microsoft Planner plans via the Microsoft Graph SDK, and for monitoring
task completion progress.

Public API
----------
- :class:`PlannerClient` — authenticated Graph client wrapper
- :class:`TasksLoader` — Schema.org integrity task JSON-LD file loader
- :class:`TasksSync` — sync integrity tasks to Planner plans/buckets/tasks (primary)
- :class:`ResponsibilitiesLoader` — responsibility JSON-LD file loader (legacy)
- :class:`PlannerSync` — sync responsibilities to Planner plans/buckets/tasks (legacy)
- :class:`PlannerMonitor` — query task completion status per CXO/dimension
"""

from __future__ import annotations

from planner.client import PlannerClient
from planner.responsibilities import ResponsibilitiesLoader
from planner.sync import PlannerMonitor, PlannerSync, TasksSync
from planner.tasks import TasksLoader

__all__ = [
    "PlannerClient",
    "PlannerMonitor",
    "PlannerSync",
    "ResponsibilitiesLoader",
    "TasksLoader",
    "TasksSync",
]
