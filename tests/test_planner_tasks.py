"""Tests for planner.tasks — Erhard integrity words-given loader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from planner.tasks import IntegrityCleanup, IntegrityRegister, WordGiven, WordsLoader


@pytest.fixture()
def integrity_dir(tmp_path: Path) -> Path:
    """Build a minimal mind tree with two agents having Integrity files."""
    for agent_id, role, legend in [
        ("ceo", "CEO", "Steve Jobs"),
        ("cfo", "CFO", "Warren Buffett"),
    ]:
        integrity_path = tmp_path / agent_id / "Integrity"
        integrity_path.mkdir(parents=True)
        doc = {
            "@context": "https://asisaga.com/contexts/integrity.jsonld",
            "@id": f"agent:{agent_id}/integrity",
            "@type": "IntegrityRegister",
            "role": role,
            "legend": legend,
            "erhard_principle": (
                f"As {role}, integrity means honouring every word I give."
            ),
            "words_given": [
                {
                    "@type": "WordGiven",
                    "wordId": f"{role}-WRD-001",
                    "name": f"Deliver the {role} Strategy",
                    "word": f"I will deliver a documented {role} strategy.",
                    "by_when": "Before the first sprint",
                    "honoring_looks_like": f"The {role} strategy is published.",
                    "word_status": "honoring",
                },
                {
                    "@type": "WordGiven",
                    "wordId": f"{role}-WRD-002",
                    "name": f"Build the {role} Framework",
                    "word": f"I will build the {role} framework.",
                    "by_when": "End of Q3 2026",
                    "honoring_looks_like": f"The {role} framework is deployed.",
                    "word_status": "out_of_integrity",
                    "cleanup": {
                        "acknowledged": f"I did not deliver the {role} framework by the committed date.",
                        "amends": "I will present the partial work at the next boardroom.",
                        "revised_word": f"I will deliver the completed {role} framework by Q4 2026.",
                        "revised_by_when": "End of Q4 2026",
                    },
                },
            ],
        }
        (integrity_path / "integrity.jsonld").write_text(
            json.dumps(doc), encoding="utf-8"
        )
    # Agent without Integrity dir
    (tmp_path / "coo").mkdir()
    return tmp_path


class TestWordsLoader:
    """Unit tests for WordsLoader."""

    def test_load_agent_returns_register(self, integrity_dir: Path) -> None:
        loader = WordsLoader(mind_dir=integrity_dir)
        register = loader.load_agent("ceo")
        assert register is not None
        assert isinstance(register, IntegrityRegister)
        assert register.role == "CEO"
        assert register.legend == "Steve Jobs"
        assert register.agent_id == "ceo"

    def test_load_agent_words_count(self, integrity_dir: Path) -> None:
        loader = WordsLoader(mind_dir=integrity_dir)
        register = loader.load_agent("ceo")
        assert register is not None
        assert len(register.words_given) == 2

    def test_load_agent_erhard_principle(self, integrity_dir: Path) -> None:
        loader = WordsLoader(mind_dir=integrity_dir)
        register = loader.load_agent("ceo")
        assert register is not None
        assert "integrity" in register.erhard_principle.lower()

    def test_load_agent_word_fields(self, integrity_dir: Path) -> None:
        loader = WordsLoader(mind_dir=integrity_dir)
        register = loader.load_agent("ceo")
        assert register is not None
        word = register.words_given[0]
        assert isinstance(word, WordGiven)
        assert word.word_id == "CEO-WRD-001"
        assert word.name == "Deliver the CEO Strategy"
        assert word.word.startswith("I will")
        assert word.by_when == "Before the first sprint"
        assert "published" in word.honoring_looks_like
        assert word.word_status == "honoring"
        assert word.cleanup is None
        assert word.planner_task_id is None

    def test_load_agent_word_with_cleanup(self, integrity_dir: Path) -> None:
        loader = WordsLoader(mind_dir=integrity_dir)
        register = loader.load_agent("ceo")
        assert register is not None
        word = register.words_given[1]
        assert word.word_status == "out_of_integrity"
        assert isinstance(word.cleanup, IntegrityCleanup)
        assert word.cleanup.acknowledged.startswith("I did not")
        assert word.cleanup.amends != ""
        assert word.cleanup.revised_word.startswith("I will")
        assert word.cleanup.revised_by_when == "End of Q4 2026"

    def test_load_agent_missing_returns_none(self, integrity_dir: Path) -> None:
        loader = WordsLoader(mind_dir=integrity_dir)
        result = loader.load_agent("coo")
        assert result is None

    def test_load_agent_nonexistent_agent_returns_none(self, integrity_dir: Path) -> None:
        loader = WordsLoader(mind_dir=integrity_dir)
        result = loader.load_agent("ghost")
        assert result is None

    def test_available_agents_lists_agents_with_integrity(self, integrity_dir: Path) -> None:
        loader = WordsLoader(mind_dir=integrity_dir)
        agents = loader.available_agents()
        assert set(agents) == {"ceo", "cfo"}
        assert "coo" not in agents

    def test_available_agents_empty_when_no_mind_dir(self, tmp_path: Path) -> None:
        loader = WordsLoader(mind_dir=tmp_path / "nonexistent")
        assert loader.available_agents() == []

    def test_jsonld_id_is_populated(self, integrity_dir: Path) -> None:
        loader = WordsLoader(mind_dir=integrity_dir)
        register = loader.load_agent("ceo")
        assert register is not None
        assert register.jsonld_id == "agent:ceo/integrity"
