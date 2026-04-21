"""Tests for planner.tasks — Integrity task JSON-LD loader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from planner.tasks import IntegrityPlan, IntegrityTask, TasksLoader


@pytest.fixture()
def integrity_dir(tmp_path: Path) -> Path:
    """Build a minimal mind tree with two agents having Integrity files."""
    for agent_id, role, legend, task_prefix in [
        ("ceo", "CEO", "Steve Jobs", "CEO"),
        ("cfo", "CFO", "Warren Buffett", "CFO"),
    ]:
        integrity_path = tmp_path / agent_id / "Integrity"
        integrity_path.mkdir(parents=True)
        doc = {
            "@context": "https://asisaga.com/contexts/integrity.jsonld",
            "@id": f"agent:{agent_id}/integrity",
            "@type": "IntegrityPlan",
            "role": role,
            "legend": legend,
            "purpose": f"Towards implementation of ASI Saga and Business Infinity — {role} tasks.",
            "tasks": [
                {
                    "@type": "schema:Action",
                    "taskId": f"{task_prefix}-INT-001",
                    "name": f"Define {role} Strategy",
                    "description": f"Detailed strategy task for {role}.",
                    "actionStatus": "schema:ActiveActionStatus",
                    "result": f"A documented {role} strategy.",
                },
                {
                    "@type": "schema:Action",
                    "taskId": f"{task_prefix}-INT-002",
                    "name": f"Build {role} Framework",
                    "description": f"Framework task for {role}.",
                    "actionStatus": "schema:PotentialActionStatus",
                },
            ],
        }
        (integrity_path / "integrity.jsonld").write_text(
            json.dumps(doc), encoding="utf-8"
        )
    # Agent without Integrity dir
    (tmp_path / "coo").mkdir()
    return tmp_path


class TestTasksLoader:
    """Unit tests for TasksLoader."""

    def test_load_agent_returns_plan(self, integrity_dir: Path) -> None:
        loader = TasksLoader(mind_dir=integrity_dir)
        plan = loader.load_agent("ceo")
        assert plan is not None
        assert isinstance(plan, IntegrityPlan)
        assert plan.role == "CEO"
        assert plan.legend == "Steve Jobs"
        assert plan.agent_id == "ceo"

    def test_load_agent_tasks_count(self, integrity_dir: Path) -> None:
        loader = TasksLoader(mind_dir=integrity_dir)
        plan = loader.load_agent("ceo")
        assert plan is not None
        assert len(plan.tasks) == 2

    def test_load_agent_task_fields(self, integrity_dir: Path) -> None:
        loader = TasksLoader(mind_dir=integrity_dir)
        plan = loader.load_agent("ceo")
        assert plan is not None
        task = plan.tasks[0]
        assert isinstance(task, IntegrityTask)
        assert task.task_id == "CEO-INT-001"
        assert task.name == "Define CEO Strategy"
        assert task.action_status == "schema:ActiveActionStatus"
        assert task.result == "A documented CEO strategy."
        assert task.planner_task_id is None

    def test_load_agent_task_without_result(self, integrity_dir: Path) -> None:
        loader = TasksLoader(mind_dir=integrity_dir)
        plan = loader.load_agent("ceo")
        assert plan is not None
        task = plan.tasks[1]
        assert task.result == ""

    def test_load_agent_missing_returns_none(self, integrity_dir: Path) -> None:
        loader = TasksLoader(mind_dir=integrity_dir)
        result = loader.load_agent("coo")
        assert result is None

    def test_load_agent_nonexistent_agent_returns_none(self, integrity_dir: Path) -> None:
        loader = TasksLoader(mind_dir=integrity_dir)
        result = loader.load_agent("ghost")
        assert result is None

    def test_available_agents_lists_agents_with_integrity(self, integrity_dir: Path) -> None:
        loader = TasksLoader(mind_dir=integrity_dir)
        agents = loader.available_agents()
        assert set(agents) == {"ceo", "cfo"}
        assert "coo" not in agents

    def test_available_agents_empty_when_no_mind_dir(self, tmp_path: Path) -> None:
        loader = TasksLoader(mind_dir=tmp_path / "nonexistent")
        assert loader.available_agents() == []

    def test_jsonld_id_is_populated(self, integrity_dir: Path) -> None:
        loader = TasksLoader(mind_dir=integrity_dir)
        plan = loader.load_agent("ceo")
        assert plan is not None
        assert plan.jsonld_id == "agent:ceo/integrity"
