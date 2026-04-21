"""JSON-LD responsibility file loader for the Planner integration.

Reads the structured responsibility JSON-LD files produced by PR #35
from ``boardroom/mind/{agent_id}/Responsibilities/`` and returns them
as plain Python dataclasses for consumption by :mod:`~business_infinity.planner.sync`.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from business_infinity._paths import PROJECT_ROOT

logger = logging.getLogger(__name__)

__all__ = ["Responsibility", "ResponsibilitiesLoader", "RoleResponsibilities"]

# Canonical path to boardroom mind directory relative to project root.
_MIND_DIR = PROJECT_ROOT / "boardroom" / "mind"

# Dimension slug → JSON-LD "dimension" value mapping
_DIMENSION_FILE_NAMES = {
    "entrepreneur": "Entrepreneur",
    "manager": "Manager",
    "domain-expert": "DomainExpert",
}


# ── Data classes ─────────────────────────────────────────────────────────────


@dataclass
class Responsibility:
    """A single committed responsibility extracted from a JSON-LD file.

    Attributes
    ----------
    title:
        Short noun-phrase title.
    commitment:
        First-person declaration starting with "I am the committed source of".
    scope:
        Domain and boundaries this responsibility covers.
    accountability:
        Concrete, observable deliverable proving the responsibility is honoured.
    planner_task_id:
        Microsoft Planner task ID, populated after syncing (may be *None*).
    """

    title: str
    commitment: str
    scope: str
    accountability: str
    planner_task_id: Optional[str] = None


@dataclass
class RoleResponsibilities:
    """All responsibilities for one CXO role in one dimension.

    Attributes
    ----------
    agent_id:
        Short agent identifier (e.g. ``"ceo"``, ``"cfo"``).
    role:
        Human-readable role label (e.g. ``"CEO"``).
    dimension:
        Dimension enum value: ``"Entrepreneur"`` | ``"Manager"`` | ``"DomainExpert"``.
    dimension_slug:
        File-system slug (e.g. ``"entrepreneur"``).
    dimension_frame:
        Narrative description of this dimension for this role.
    erhard_principle:
        First-person ontological ownership declaration.
    responsibilities:
        Ordered list of :class:`Responsibility` items.
    jsonld_id:
        The ``@id`` value from the source file.
    """

    agent_id: str
    role: str
    dimension: str
    dimension_slug: str
    dimension_frame: str
    erhard_principle: str
    responsibilities: List[Responsibility] = field(default_factory=list)
    jsonld_id: str = ""


# ── Loader ───────────────────────────────────────────────────────────────────


class ResponsibilitiesLoader:
    """Loads CXO responsibility JSON-LD files from the boardroom/mind tree.

    Parameters
    ----------
    mind_dir:
        Override for the ``boardroom/mind`` directory path.  Defaults to
        the canonical location derived from :data:`~business_infinity._paths.PROJECT_ROOT`.
    """

    def __init__(self, mind_dir: Optional[Path] = None) -> None:
        self._mind_dir = mind_dir or _MIND_DIR

    # ── Public API ───────────────────────────────────────────────────────────

    def load_agent(self, agent_id: str) -> List[RoleResponsibilities]:
        """Load all three dimension files for *agent_id*.

        Parameters
        ----------
        agent_id:
            Short agent identifier, e.g. ``"ceo"``.

        Returns
        -------
        list[RoleResponsibilities]
            One entry per dimension (up to three).  Dimensions whose files are
            absent are silently skipped with a warning log entry.
        """
        results: List[RoleResponsibilities] = []
        for slug in _DIMENSION_FILE_NAMES:
            data = self._load_file(agent_id, slug)
            if data is not None:
                results.append(data)
        return results

    def load_dimension(self, agent_id: str, dimension_slug: str) -> Optional[RoleResponsibilities]:
        """Load a single dimension file for *agent_id*.

        Parameters
        ----------
        agent_id:
            Short agent identifier, e.g. ``"ceo"``.
        dimension_slug:
            Dimension slug: ``"entrepreneur"``, ``"manager"``, or ``"domain-expert"``.

        Returns
        -------
        RoleResponsibilities or None
            Parsed data, or *None* if the file does not exist.
        """
        if dimension_slug not in _DIMENSION_FILE_NAMES:
            raise ValueError(
                f"Unknown dimension slug {dimension_slug!r}. "
                f"Must be one of: {list(_DIMENSION_FILE_NAMES)}"
            )
        return self._load_file(agent_id, dimension_slug)

    def available_agents(self) -> List[str]:
        """Return agent IDs for which Responsibilities directories exist."""
        agents: List[str] = []
        if not self._mind_dir.is_dir():
            return agents
        for child in sorted(self._mind_dir.iterdir()):
            if child.is_dir() and (child / "Responsibilities").is_dir():
                agents.append(child.name)
        return agents

    # ── Private helpers ──────────────────────────────────────────────────────

    def _load_file(self, agent_id: str, dimension_slug: str) -> Optional[RoleResponsibilities]:
        """Read and parse one JSON-LD responsibility file."""
        path = (
            self._mind_dir
            / agent_id
            / "Responsibilities"
            / f"{dimension_slug}.jsonld"
        )
        if not path.exists():
            logger.warning("Responsibility file not found: %s", path)
            return None

        with path.open(encoding="utf-8") as fh:
            raw = json.load(fh)

        responsibilities = [
            Responsibility(
                title=r["title"],
                commitment=r["commitment"],
                scope=r["scope"],
                accountability=r["accountability"],
                planner_task_id=r.get("planner_task_id"),
            )
            for r in raw.get("responsibilities", [])
        ]

        return RoleResponsibilities(
            agent_id=agent_id,
            role=raw["role"],
            dimension=raw["dimension"],
            dimension_slug=dimension_slug,
            dimension_frame=raw["dimension_frame"],
            erhard_principle=raw["erhard_principle"],
            responsibilities=responsibilities,
            jsonld_id=raw.get("@id", ""),
        )
