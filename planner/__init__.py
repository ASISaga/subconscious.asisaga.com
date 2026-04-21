"""Microsoft Planner integration for CXO task and responsibility planning.

Provides tools for syncing CXO integrity words-given and responsibilities to
Microsoft Planner plans via the Microsoft Graph SDK, and for monitoring
task completion progress.

Integrity is implemented through Werner Erhard's ontological definition:
**Integrity = Honoring Your Word**. Each CXO's Integrity register records the
explicit words given, by-when, what honouring looks like, and — when a word
cannot be kept — the cleanup protocol.

Public API
----------
- :class:`PlannerClient` — authenticated Graph client wrapper
- :class:`WordsLoader` — integrity words-given JSON-LD file loader (primary)
- :class:`TasksSync` — sync words-given to Planner plans/buckets/tasks (primary)
- :class:`ResponsibilitiesLoader` — responsibility JSON-LD file loader (legacy)
- :class:`PlannerSync` — sync responsibilities to Planner plans/buckets/tasks (legacy)
- :class:`PlannerMonitor` — query task completion status per CXO/dimension
"""

from __future__ import annotations

from planner.client import PlannerClient
from planner.responsibilities import ResponsibilitiesLoader
from planner.sync import PlannerMonitor, PlannerSync, TasksSync
from planner.tasks import WordsLoader

__all__ = [
    "PlannerClient",
    "PlannerMonitor",
    "PlannerSync",
    "ResponsibilitiesLoader",
    "TasksSync",
    "WordsLoader",
]
