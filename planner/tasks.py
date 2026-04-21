"""Schema.org JSON-LD integrity task loader for the Planner integration.

Reads the structured integrity task JSON-LD files from
``mind/{agent_id}/Integrity/integrity.jsonld`` and returns them as plain
Python dataclasses for consumption by :mod:`~planner.sync`.

Each ``integrity.jsonld`` file declares a list of Schema.org ``Action``
tasks towards implementation of ASI Saga and Business Infinity, following
the ``IntegrityPlan`` schema at ``schemas/integrity.schema.json``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

__all__ = ["IntegrityTask", "IntegrityPlan", "TasksLoader"]

# Canonical path to mind directory relative to this file.
_MIND_DIR = Path(__file__).parent.parent / "mind"

# Name of the integrity task file within each Integrity/ directory.
_INTEGRITY_FILENAME = "integrity.jsonld"


# ── Data classes ─────────────────────────────────────────────────────────────


@dataclass
class IntegrityTask:
    """A single Schema.org Action task extracted from an integrity JSON-LD file.

    Attributes
    ----------
    task_id:
        Unique task identifier (e.g. ``"CEO-INT-001"``).
    name:
        Short, imperative task name.
    description:
        Detailed description of what must be done and why it matters.
    action_status:
        Schema.org ActionStatus URI (e.g. ``"schema:PotentialActionStatus"``).
    result:
        Concrete deliverable produced when the task is complete.
    planner_task_id:
        Microsoft Planner task ID, populated after syncing (may be *None*).
    """

    task_id: str
    name: str
    description: str
    action_status: str
    result: str = ""
    planner_task_id: str | None = None


@dataclass
class IntegrityPlan:
    """All integrity tasks for one CXO agent.

    Attributes
    ----------
    agent_id:
        Short agent identifier (e.g. ``"ceo"``, ``"cfo"``).
    role:
        Human-readable role label (e.g. ``"CEO"``).
    legend:
        The archetype or legend embodied by this agent.
    purpose:
        The overarching purpose of this integrity plan.
    tasks:
        Ordered list of :class:`IntegrityTask` items.
    jsonld_id:
        The ``@id`` value from the source file.
    """

    agent_id: str
    role: str
    legend: str
    purpose: str
    tasks: list[IntegrityTask] = field(default_factory=list)
    jsonld_id: str = ""


# ── Loader ───────────────────────────────────────────────────────────────────


class TasksLoader:
    """Loads CXO integrity task JSON-LD files from the mind tree.

    Parameters
    ----------
    mind_dir:
        Override for the ``mind`` directory path.  Defaults to the
        canonical location relative to this module.
    """

    def __init__(self, mind_dir: Path | None = None) -> None:
        self._mind_dir = mind_dir or _MIND_DIR

    # ── Public API ───────────────────────────────────────────────────────────

    def load_agent(self, agent_id: str) -> IntegrityPlan | None:
        """Load the integrity plan for *agent_id*.

        Parameters
        ----------
        agent_id:
            Short agent identifier, e.g. ``"ceo"``.

        Returns
        -------
        IntegrityPlan or None
            Parsed data, or *None* if the file does not exist.
        """
        return self._load_file(agent_id)

    def available_agents(self) -> list[str]:
        """Return agent IDs for which Integrity directories exist."""
        agents: list[str] = []
        if not self._mind_dir.is_dir():
            return agents
        for child in sorted(self._mind_dir.iterdir()):
            if child.is_dir() and (child / "Integrity" / _INTEGRITY_FILENAME).exists():
                agents.append(child.name)
        return agents

    # ── Private helpers ──────────────────────────────────────────────────────

    def _load_file(self, agent_id: str) -> IntegrityPlan | None:
        """Read and parse the integrity JSON-LD file for *agent_id*."""
        path = self._mind_dir / agent_id / "Integrity" / _INTEGRITY_FILENAME
        if not path.exists():
            logger.warning("Integrity file not found: %s", path)
            return None

        with path.open(encoding="utf-8") as fh:
            raw = json.load(fh)

        tasks = [
            IntegrityTask(
                task_id=t["taskId"],
                name=t["name"],
                description=t["description"],
                action_status=t["actionStatus"],
                result=t.get("result", ""),
                planner_task_id=t.get("planner_task_id"),
            )
            for t in raw.get("tasks", [])
        ]

        return IntegrityPlan(
            agent_id=agent_id,
            role=raw["role"],
            legend=raw.get("legend", ""),
            purpose=raw["purpose"],
            tasks=tasks,
            jsonld_id=raw.get("@id", ""),
        )
