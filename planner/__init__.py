"""Microsoft Planner integration for CXO responsibility planning and monitoring.

Provides tools for syncing CXO responsibility JSON-LD files to Microsoft
Planner plans via the Microsoft Graph SDK, and for monitoring task completion
progress against declared accountabilities.

Public API
----------
- :class:`PlannerClient` — authenticated Graph client wrapper
- :class:`ResponsibilitiesLoader` — JSON-LD file loader
- :class:`PlannerSync` — sync responsibilities to Planner plans/buckets/tasks
- :class:`PlannerMonitor` — query task completion status per CXO/dimension
"""

from __future__ import annotations

from business_infinity.planner.client import PlannerClient
from business_infinity.planner.responsibilities import ResponsibilitiesLoader
from business_infinity.planner.sync import PlannerMonitor, PlannerSync

__all__ = [
    "PlannerClient",
    "PlannerMonitor",
    "PlannerSync",
    "ResponsibilitiesLoader",
]
