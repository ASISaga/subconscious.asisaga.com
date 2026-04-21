"""Schema.org JSON-LD integrity word-given loader for the Planner integration.

Reads the structured integrity JSON-LD files from
``mind/{agent_id}/Integrity/integrity.jsonld`` and returns them as plain
Python dataclasses for consumption by :mod:`~planner.sync`.

Each ``integrity.jsonld`` file is an ``IntegrityRegister`` — a register of
*words given* by a CXO agent towards implementation of ASI Saga and Business
Infinity, authored through Werner Erhard's ontological definition of integrity:

    **Integrity = Honoring Your Word**

    Integrity is not a moral concept — it is the condition of wholeness and
    workability. A word given is a specific, first-person commitment bound to a
    *by-when*. Honouring it means doing what you said, by when you said it.
    Being out of integrity means cleaning it up: acknowledge, make amends,
    give a revised word.

Each :class:`WordGiven` records the word, the by-when, what honouring looks
like in observable terms, the current status, and — when a word cannot be kept
— the cleanup protocol.

The schema is defined in ``schemas/integrity.schema.json``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

__all__ = ["WordGiven", "IntegrityCleanup", "IntegrityRegister", "WordsLoader"]

# Canonical path to mind directory relative to this file.
_MIND_DIR = Path(__file__).parent.parent / "mind"

# Name of the integrity file within each Integrity/ directory.
_INTEGRITY_FILENAME = "integrity.jsonld"


# ── Data classes ─────────────────────────────────────────────────────────────


@dataclass
class IntegrityCleanup:
    """The three-step cleanup protocol when a word cannot be kept.

    Attributes
    ----------
    acknowledged:
        Explicit statement of what word was given and could not be honoured.
    revised_word:
        The new commitment, restated in first-person form.
    revised_by_when:
        The new completion target.
    amends:
        What was done or will be done to address the impact (optional).
    """

    acknowledged: str
    revised_word: str
    revised_by_when: str
    amends: str = ""


@dataclass
class WordGiven:
    """A single word given — an explicit first-person commitment.

    Authored through Werner Erhard's ontological integrity framework:
    a word given is not a wish or a plan but a declaration that binds the
    speaker to a specific outcome by a specific time.

    Attributes
    ----------
    word_id:
        Unique identifier (e.g. ``"CEO-WRD-001"``).
    name:
        Short label used as the Planner task title.
    word:
        The explicit commitment in first-person form (begins with "I will"
        or "I give my word").
    by_when:
        The specific completion target — date, milestone, or condition.
    honoring_looks_like:
        Observable, verifiable evidence that this word has been honoured.
    word_status:
        Current integrity status: ``"honoring"``, ``"complete"``, or
        ``"out_of_integrity"``.
    cleanup:
        Cleanup record populated only when ``word_status`` is
        ``"out_of_integrity"``.
    planner_task_id:
        Microsoft Planner task ID once synced (may be *None*).
    """

    word_id: str
    name: str
    word: str
    by_when: str
    honoring_looks_like: str
    word_status: str
    cleanup: IntegrityCleanup | None = None
    planner_task_id: str | None = None


@dataclass
class IntegrityRegister:
    """The complete integrity register for one CXO agent.

    A register of all words given by this agent towards implementation of
    ASI Saga and Business Infinity, framed through Werner Erhard's
    definition of integrity as honouring your word.

    Attributes
    ----------
    agent_id:
        Short agent identifier (e.g. ``"ceo"``, ``"cfo"``).
    role:
        Human-readable role label (e.g. ``"CEO"``).
    legend:
        The archetype or legend embodied by this agent.
    erhard_principle:
        First-person statement of how Erhard's integrity principle applies
        to this role.
    words_given:
        Ordered list of :class:`WordGiven` items.
    jsonld_id:
        The ``@id`` value from the source file.
    """

    agent_id: str
    role: str
    legend: str
    erhard_principle: str
    words_given: list[WordGiven] = field(default_factory=list)
    jsonld_id: str = ""


# ── Loader ───────────────────────────────────────────────────────────────────


class WordsLoader:
    """Loads CXO integrity JSON-LD registers from the mind tree.

    Parameters
    ----------
    mind_dir:
        Override for the ``mind`` directory path.  Defaults to the
        canonical location relative to this module.
    """

    def __init__(self, mind_dir: Path | None = None) -> None:
        self._mind_dir = mind_dir or _MIND_DIR

    # ── Public API ───────────────────────────────────────────────────────────

    def load_agent(self, agent_id: str) -> IntegrityRegister | None:
        """Load the integrity register for *agent_id*.

        Parameters
        ----------
        agent_id:
            Short agent identifier, e.g. ``"ceo"``.

        Returns
        -------
        IntegrityRegister or None
            Parsed register, or *None* if the file does not exist.
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

    def _load_file(self, agent_id: str) -> IntegrityRegister | None:
        """Read and parse the integrity JSON-LD file for *agent_id*."""
        path = self._mind_dir / agent_id / "Integrity" / _INTEGRITY_FILENAME
        if not path.exists():
            logger.warning("Integrity file not found: %s", path)
            return None

        with path.open(encoding="utf-8") as fh:
            raw = json.load(fh)

        words_given = [
            WordGiven(
                word_id=w["wordId"],
                name=w["name"],
                word=w["word"],
                by_when=w["by_when"],
                honoring_looks_like=w["honoring_looks_like"],
                word_status=w["word_status"],
                cleanup=self._parse_cleanup(w.get("cleanup")),
                planner_task_id=w.get("planner_task_id"),
            )
            for w in raw.get("words_given", [])
        ]

        return IntegrityRegister(
            agent_id=agent_id,
            role=raw["role"],
            legend=raw.get("legend", ""),
            erhard_principle=raw.get("erhard_principle", ""),
            words_given=words_given,
            jsonld_id=raw.get("@id", ""),
        )

    @staticmethod
    def _parse_cleanup(raw: dict | None) -> IntegrityCleanup | None:
        """Parse a cleanup dict into an :class:`IntegrityCleanup`, or *None*."""
        if raw is None:
            return None
        return IntegrityCleanup(
            acknowledged=raw["acknowledged"],
            revised_word=raw["revised_word"],
            revised_by_when=raw["revised_by_when"],
            amends=raw.get("amends", ""),
        )
