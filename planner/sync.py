"""Microsoft Planner sync engine for CXO tasks and responsibilities.

Provides two sync engines:

* :class:`TasksSync` — syncs integrity tasks from ``mind/{agent}/Integrity/``
  into Microsoft Planner.  This is the primary sync path.

* :class:`PlannerSync` — legacy sync of responsibilities from
  ``mind/{agent}/Responsibilities/`` into Microsoft Planner (retained for
  backward compatibility).

Planner structure for tasks (TasksSync)
----------------------------------------
::

    Plan  ── "{ROLE} Integrity"   (one per CXO, owned by a Microsoft 365 group)
    └── Bucket  "ASI Saga & Business Infinity"
        ├── Task  "{task.name}"
        └── ...

Planner structure for responsibilities (PlannerSync — legacy)
--------------------------------------------------------------
::

    Plan  ── "{ROLE} Responsibilities"   (one per CXO)
    ├── Bucket  "Entrepreneur"
    ├── Bucket  "Manager"
    └── Bucket  "Domain Expert"

Each task carries:
- **title** — ``task.name`` / ``responsibility.title``
- **description** (via task details) — task description or commitment + scope + accountability
- **percent_complete** — updated independently by the owning CXO

Environment variables
---------------------
``PLANNER_GROUP_ID``
    Microsoft 365 group ID that will own every CXO plan.  This group should
    include all CXO members as owners/members.

``PLANNER_GROUP_ID_{ROLE}``
    Per-role override (e.g. ``PLANNER_GROUP_ID_CEO``).  Takes precedence over
    the default ``PLANNER_GROUP_ID`` when present.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from msgraph.generated.models.o_data_errors.o_data_error import ODataError
from msgraph.generated.models.planner_bucket import PlannerBucket
from msgraph.generated.models.planner_container_type import PlannerContainerType
from msgraph.generated.models.planner_plan import PlannerPlan
from msgraph.generated.models.planner_plan_container import PlannerPlanContainer
from msgraph.generated.models.planner_task import PlannerTask
from msgraph.generated.models.planner_task_details import PlannerTaskDetails

from planner.client import PlannerClient
from planner.responsibilities import (
    ResponsibilitiesLoader,
    RoleResponsibilities,
)
from planner.tasks import IntegrityPlan, TasksLoader

logger = logging.getLogger(__name__)

__all__ = ["PlannerMonitor", "PlannerSync", "SyncResult", "TaskStatus", "TasksSync"]

# Human-readable bucket names per dimension slug.
_BUCKET_NAMES: dict[str, str] = {
    "entrepreneur": "Entrepreneur",
    "manager": "Manager",
    "domain-expert": "Domain Expert",
}


# ── Result dataclasses ────────────────────────────────────────────────────────


@dataclass
class TaskStatus:
    """Completion status of a single Planner task.

    Attributes
    ----------
    title:
        Responsibility title.
    task_id:
        Microsoft Planner task ID.
    percent_complete:
        Completion percentage (0–100).
    dimension:
        Dimension the task belongs to.
    """

    title: str
    task_id: str
    percent_complete: int
    dimension: str


@dataclass
class SyncResult:
    """Outcome of a full CXO responsibility sync.

    Attributes
    ----------
    agent_id:
        Short agent identifier.
    role:
        Human-readable role label.
    plan_id:
        Planner plan ID (created or matched).
    plan_title:
        Planner plan title.
    buckets_synced:
        Number of Planner buckets created/verified.
    tasks_created:
        Number of new tasks created.
    tasks_skipped:
        Number of tasks that already existed (not duplicated).
    errors:
        Per-task error messages encountered during sync.
    """

    agent_id: str
    role: str
    plan_id: str
    plan_title: str
    buckets_synced: int = 0
    tasks_created: int = 0
    tasks_skipped: int = 0
    errors: list[str] = field(default_factory=list)


# ── PlannerSync ───────────────────────────────────────────────────────────────


class PlannerSync:
    """Syncs CXO responsibilities from JSON-LD files into Microsoft Planner.

    Parameters
    ----------
    planner_client:
        Authenticated :class:`~business_infinity.planner.client.PlannerClient`.
    loader:
        :class:`~business_infinity.planner.responsibilities.ResponsibilitiesLoader`
        instance.  A default instance is created when *None*.
    """

    def __init__(
        self,
        planner_client: PlannerClient,
        loader: ResponsibilitiesLoader | None = None,
    ) -> None:
        self._client = planner_client.graph
        self._loader = loader or ResponsibilitiesLoader()

    # ── Public API ───────────────────────────────────────────────────────────

    async def sync_agent(self, agent_id: str, group_id: str | None = None) -> SyncResult:
        """Sync all responsibility dimensions for *agent_id* to Planner.

        Creates one plan per CXO (if not already present), then creates
        one bucket per dimension and one task per responsibility.  Existing
        tasks (matched by title) are skipped to avoid duplicates.

        Parameters
        ----------
        agent_id:
            Short agent identifier, e.g. ``"ceo"``.
        group_id:
            Microsoft 365 group ID that will own the plan.  When *None*,
            resolved from the ``PLANNER_GROUP_ID_{ROLE}`` or
            ``PLANNER_GROUP_ID`` environment variables.

        Returns
        -------
        SyncResult
            Summary of created buckets and tasks.
        """
        dimensions = self._loader.load_agent(agent_id)
        if not dimensions:
            raise ValueError(f"No responsibility files found for agent: {agent_id!r}")

        role = dimensions[0].role
        resolved_group_id = group_id or self._resolve_group_id(role)

        plan_title = f"{role} Responsibilities"
        plan_id = await self._get_or_create_plan(plan_title, resolved_group_id)

        result = SyncResult(
            agent_id=agent_id,
            role=role,
            plan_id=plan_id,
            plan_title=plan_title,
        )

        for dim_data in dimensions:
            await self._sync_dimension(dim_data, plan_id, result)

        logger.info(
            "Sync complete for %s: plan=%s buckets=%d tasks_created=%d skipped=%d errors=%d",
            agent_id,
            plan_id,
            result.buckets_synced,
            result.tasks_created,
            result.tasks_skipped,
            len(result.errors),
        )
        return result

    async def sync_dimension(
        self,
        agent_id: str,
        dimension_slug: str,
        group_id: str | None = None,
    ) -> SyncResult:
        """Sync a single dimension for *agent_id* to Planner.

        Parameters
        ----------
        agent_id:
            Short agent identifier.
        dimension_slug:
            ``"entrepreneur"``, ``"manager"``, or ``"domain-expert"``.
        group_id:
            Optional Microsoft 365 group ID override.

        Returns
        -------
        SyncResult
            Summary of the sync operation.
        """
        dim_data = self._loader.load_dimension(agent_id, dimension_slug)
        if dim_data is None:
            raise ValueError(
                f"No responsibility file found for agent={agent_id!r} "
                f"dimension={dimension_slug!r}"
            )

        resolved_group_id = group_id or self._resolve_group_id(dim_data.role)
        plan_title = f"{dim_data.role} Responsibilities"
        plan_id = await self._get_or_create_plan(plan_title, resolved_group_id)

        result = SyncResult(
            agent_id=agent_id,
            role=dim_data.role,
            plan_id=plan_id,
            plan_title=plan_title,
        )
        await self._sync_dimension(dim_data, plan_id, result)
        return result

    # ── Private helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _resolve_group_id(role: str) -> str:
        """Resolve the Microsoft 365 group ID for *role* from env vars."""
        return _resolve_group_id(role)

    async def _get_or_create_plan(self, title: str, group_id: str) -> str:
        """Return the plan ID for *title* in *group_id*, creating if absent."""
        plans_response = await self._client.planner.plans.get()
        if plans_response and plans_response.value:
            for plan in plans_response.value:
                if plan.title == title:
                    logger.debug("Found existing plan: %s (%s)", title, plan.id)
                    return plan.id

        new_plan = PlannerPlan()
        new_plan.title = title
        container = PlannerPlanContainer()
        container.container_id = group_id
        container.type = PlannerContainerType.Group
        new_plan.container = container

        created = await self._client.planner.plans.post(new_plan)
        logger.info("Created new Planner plan: %s (%s)", title, created.id)
        return created.id

    async def _get_or_create_bucket(self, plan_id: str, bucket_name: str) -> str:
        """Return bucket ID for *bucket_name* in *plan_id*, creating if absent."""
        buckets_response = await (
            self._client.planner.plans.by_planner_plan_id(plan_id).buckets.get()
        )
        if buckets_response and buckets_response.value:
            for bucket in buckets_response.value:
                if bucket.name == bucket_name:
                    logger.debug("Found existing bucket: %s (%s)", bucket_name, bucket.id)
                    return bucket.id

        new_bucket = PlannerBucket()
        new_bucket.name = bucket_name
        new_bucket.plan_id = plan_id
        new_bucket.order_hint = " !"

        created = await self._client.planner.buckets.post(new_bucket)
        logger.info("Created new bucket: %s (%s)", bucket_name, created.id)
        return created.id

    async def _get_existing_task_titles(self, plan_id: str) -> dict[str, str]:
        """Return a mapping of task title → task ID for all tasks in *plan_id*."""
        tasks_response = await (
            self._client.planner.plans.by_planner_plan_id(plan_id).tasks.get()
        )
        if not tasks_response or not tasks_response.value:
            return {}
        return {task.title: task.id for task in tasks_response.value if task.title}

    async def _create_task(
        self,
        plan_id: str,
        bucket_id: str,
        title: str,
        commitment: str,
        scope: str,
        accountability: str,
    ) -> str:
        """Create a Planner task and attach its description via task details."""
        new_task = PlannerTask()
        new_task.plan_id = plan_id
        new_task.bucket_id = bucket_id
        new_task.title = title
        new_task.percent_complete = 0

        created_task = await self._client.planner.tasks.post(new_task)
        task_id = created_task.id

        # Attach rich description through task details.
        details = PlannerTaskDetails()
        details.description = (
            f"COMMITMENT\n{commitment}\n\n"
            f"SCOPE\n{scope}\n\n"
            f"ACCOUNTABILITY\n{accountability}"
        )
        # Fetch task details to verify creation before patching description.
        await self._client.planner.tasks.by_planner_task_id(task_id).details.get()
        await (
            self._client.planner.tasks
            .by_planner_task_id(task_id)
            .details
            .patch(details)
        )

        logger.debug("Created task: %s (%s)", title, task_id)
        return task_id

    async def _sync_dimension(
        self,
        dim_data: RoleResponsibilities,
        plan_id: str,
        result: SyncResult,
    ) -> None:
        """Sync one dimension's responsibilities into Planner buckets/tasks."""
        bucket_name = _BUCKET_NAMES.get(dim_data.dimension_slug, dim_data.dimension)
        bucket_id = await self._get_or_create_bucket(plan_id, bucket_name)
        result.buckets_synced += 1

        existing_titles = await self._get_existing_task_titles(plan_id)

        for resp in dim_data.responsibilities:
            if resp.title in existing_titles:
                logger.debug("Skipping existing task: %s", resp.title)
                result.tasks_skipped += 1
                continue
            try:
                await self._create_task(
                    plan_id=plan_id,
                    bucket_id=bucket_id,
                    title=resp.title,
                    commitment=resp.commitment,
                    scope=resp.scope,
                    accountability=resp.accountability,
                )
                result.tasks_created += 1
            except (ODataError, ValueError, RuntimeError) as exc:
                msg = f"Failed to create task {resp.title!r}: {exc}"
                logger.error(msg)
                result.errors.append(msg)


# ── PlannerMonitor ────────────────────────────────────────────────────────────


class PlannerMonitor:
    """Queries Microsoft Planner for CXO responsibility task completion status.

    Parameters
    ----------
    planner_client:
        Authenticated :class:`~business_infinity.planner.client.PlannerClient`.
    """

    def __init__(self, planner_client: PlannerClient) -> None:
        self._client = planner_client.graph

    async def get_plan_status(self, plan_id: str) -> list[TaskStatus]:
        """Return completion status of all tasks in *plan_id*.

        Parameters
        ----------
        plan_id:
            Microsoft Planner plan ID.

        Returns
        -------
        list[TaskStatus]
            One entry per task, sorted by dimension bucket then title.
        """
        tasks_response = await (
            self._client.planner.plans.by_planner_plan_id(plan_id).tasks.get()
        )
        if not tasks_response or not tasks_response.value:
            return []

        # Fetch bucket names for dimension labelling.
        buckets_response = await (
            self._client.planner.plans.by_planner_plan_id(plan_id).buckets.get()
        )
        bucket_id_to_name: dict[str, str] = {}
        if buckets_response and buckets_response.value:
            bucket_id_to_name = {b.id: b.name for b in buckets_response.value}

        statuses: list[TaskStatus] = []
        for task in tasks_response.value:
            if not task.title:
                continue
            statuses.append(
                TaskStatus(
                    title=task.title,
                    task_id=task.id,
                    percent_complete=task.percent_complete or 0,
                    dimension=bucket_id_to_name.get(task.bucket_id or "", ""),
                )
            )

        return sorted(statuses, key=lambda s: (s.dimension, s.title))

    async def get_agent_status(
        self,
        role: str,
    ) -> list[TaskStatus] | None:
        """Return completion status for the plan titled "{role} Responsibilities".

        Parameters
        ----------
        role:
            Human-readable role label, e.g. ``"CEO"``.

        Returns
        -------
        list[TaskStatus] or None
            Task statuses, or *None* if no matching plan was found.
        """
        plan_title = f"{role} Responsibilities"
        plans_response = await self._client.planner.plans.get()
        if not plans_response or not plans_response.value:
            return None

        for plan in plans_response.value:
            if plan.title == plan_title:
                return await self.get_plan_status(plan.id)

        return None

    @staticmethod
    def summarise(statuses: list[TaskStatus]) -> dict[str, object]:
        """Return an aggregate completion summary for *statuses*.

        Returns
        -------
        dict
            Keys: ``total``, ``complete``, ``in_progress``, ``not_started``,
            ``overall_percent``, ``by_dimension``.
        """
        if not statuses:
            return {
                "total": 0,
                "complete": 0,
                "in_progress": 0,
                "not_started": 0,
                "overall_percent": 0,
                "by_dimension": {},
            }

        total = len(statuses)
        complete = sum(1 for s in statuses if s.percent_complete == 100)
        in_progress = sum(1 for s in statuses if 0 < s.percent_complete < 100)
        not_started = sum(1 for s in statuses if s.percent_complete == 0)
        overall_percent = round(sum(s.percent_complete for s in statuses) / total)

        by_dimension: dict[str, dict[str, object]] = {}
        for status in statuses:
            dim = status.dimension or "Unknown"
            if dim not in by_dimension:
                by_dimension[dim] = {"total": 0, "complete": 0, "overall_percent": 0, "_sum": 0}
            by_dimension[dim]["total"] = int(by_dimension[dim]["total"]) + 1
            by_dimension[dim]["_sum"] = int(by_dimension[dim]["_sum"]) + status.percent_complete
            if status.percent_complete == 100:
                by_dimension[dim]["complete"] = int(by_dimension[dim]["complete"]) + 1

        for dim_data in by_dimension.values():
            dim_total = int(dim_data["total"])
            dim_sum = int(dim_data.pop("_sum"))
            dim_data["overall_percent"] = round(dim_sum / dim_total) if dim_total else 0

        return {
            "total": total,
            "complete": complete,
            "in_progress": in_progress,
            "not_started": not_started,
            "overall_percent": overall_percent,
            "by_dimension": by_dimension,
        }


# ── TasksSync ─────────────────────────────────────────────────────────────────


class TasksSync:
    """Syncs CXO integrity tasks from JSON-LD files into Microsoft Planner.

    Reads ``mind/{agent_id}/Integrity/integrity.jsonld`` and creates one
    Planner plan per CXO with a single ``"ASI Saga & Business Infinity"``
    bucket containing one task per integrity task.

    Parameters
    ----------
    planner_client:
        Authenticated :class:`~planner.client.PlannerClient`.
    loader:
        :class:`~planner.tasks.TasksLoader` instance.  A default instance is
        created when *None*.
    """

    _BUCKET_NAME = "ASI Saga & Business Infinity"

    def __init__(
        self,
        planner_client: PlannerClient,
        loader: TasksLoader | None = None,
    ) -> None:
        self._client = planner_client.graph
        self._loader = loader or TasksLoader()

    # ── Public API ───────────────────────────────────────────────────────────

    async def sync_agent(self, agent_id: str, group_id: str | None = None) -> SyncResult:
        """Sync all integrity tasks for *agent_id* to Planner.

        Creates one plan per CXO (if not already present) and one task per
        integrity task inside the ``"ASI Saga & Business Infinity"`` bucket.
        Existing tasks (matched by title) are skipped to avoid duplicates.

        Parameters
        ----------
        agent_id:
            Short agent identifier, e.g. ``"ceo"``.
        group_id:
            Microsoft 365 group ID that will own the plan.  When *None*,
            resolved from the ``PLANNER_GROUP_ID_{ROLE}`` or
            ``PLANNER_GROUP_ID`` environment variables.

        Returns
        -------
        SyncResult
            Summary of created buckets and tasks.
        """
        plan_data = self._loader.load_agent(agent_id)
        if plan_data is None:
            raise ValueError(f"No integrity file found for agent: {agent_id!r}")

        resolved_group_id = group_id or _resolve_group_id(plan_data.role)
        plan_title = f"{plan_data.role} Integrity"
        plan_id = await self._get_or_create_plan(plan_title, resolved_group_id)

        result = SyncResult(
            agent_id=agent_id,
            role=plan_data.role,
            plan_id=plan_id,
            plan_title=plan_title,
        )
        await self._sync_tasks(plan_data, plan_id, result)

        logger.info(
            "TasksSync complete for %s: plan=%s tasks_created=%d skipped=%d errors=%d",
            agent_id,
            plan_id,
            result.tasks_created,
            result.tasks_skipped,
            len(result.errors),
        )
        return result

    async def sync_all(self, group_id: str | None = None) -> list[SyncResult]:
        """Sync integrity tasks for all available agents.

        Parameters
        ----------
        group_id:
            Optional Microsoft 365 group ID override applied to all plans.

        Returns
        -------
        list[SyncResult]
            One result per agent that has an ``Integrity/integrity.jsonld`` file.
        """
        results: list[SyncResult] = []
        for agent_id in self._loader.available_agents():
            results.append(await self.sync_agent(agent_id, group_id=group_id))
        return results

    # ── Private helpers ──────────────────────────────────────────────────────

    async def _get_or_create_plan(self, title: str, group_id: str) -> str:
        """Return the plan ID for *title* in *group_id*, creating if absent."""
        plans_response = await self._client.planner.plans.get()
        if plans_response and plans_response.value:
            for plan in plans_response.value:
                if plan.title == title:
                    logger.debug("Found existing plan: %s (%s)", title, plan.id)
                    return plan.id

        new_plan = PlannerPlan()
        new_plan.title = title
        container = PlannerPlanContainer()
        container.container_id = group_id
        container.type = PlannerContainerType.Group
        new_plan.container = container

        created = await self._client.planner.plans.post(new_plan)
        logger.info("Created new Planner plan: %s (%s)", title, created.id)
        return created.id

    async def _get_or_create_bucket(self, plan_id: str) -> str:
        """Return bucket ID for the integrity bucket in *plan_id*, creating if absent."""
        buckets_response = await (
            self._client.planner.plans.by_planner_plan_id(plan_id).buckets.get()
        )
        if buckets_response and buckets_response.value:
            for bucket in buckets_response.value:
                if bucket.name == self._BUCKET_NAME:
                    logger.debug("Found existing bucket: %s (%s)", self._BUCKET_NAME, bucket.id)
                    return bucket.id

        new_bucket = PlannerBucket()
        new_bucket.name = self._BUCKET_NAME
        new_bucket.plan_id = plan_id
        new_bucket.order_hint = " !"

        created = await self._client.planner.buckets.post(new_bucket)
        logger.info("Created new bucket: %s (%s)", self._BUCKET_NAME, created.id)
        return created.id

    async def _get_existing_task_titles(self, plan_id: str) -> dict[str, str]:
        """Return a mapping of task title → task ID for all tasks in *plan_id*."""
        tasks_response = await (
            self._client.planner.plans.by_planner_plan_id(plan_id).tasks.get()
        )
        if not tasks_response or not tasks_response.value:
            return {}
        return {task.title: task.id for task in tasks_response.value if task.title}

    async def _create_task(
        self,
        plan_id: str,
        bucket_id: str,
        title: str,
        description: str,
        task_id: str,
        result_text: str,
    ) -> str:
        """Create a Planner task and attach its description via task details."""
        new_task = PlannerTask()
        new_task.plan_id = plan_id
        new_task.bucket_id = bucket_id
        new_task.title = title
        new_task.percent_complete = 0

        created_task = await self._client.planner.tasks.post(new_task)
        planner_id = created_task.id

        details = PlannerTaskDetails()
        detail_lines = [f"TASK ID\n{task_id}", f"DESCRIPTION\n{description}"]
        if result_text:
            detail_lines.append(f"RESULT\n{result_text}")
        details.description = "\n\n".join(detail_lines)

        await self._client.planner.tasks.by_planner_task_id(planner_id).details.get()
        await (
            self._client.planner.tasks
            .by_planner_task_id(planner_id)
            .details
            .patch(details)
        )

        logger.debug("Created task: %s (%s)", title, planner_id)
        return planner_id

    async def _sync_tasks(
        self,
        plan_data: IntegrityPlan,
        plan_id: str,
        result: SyncResult,
    ) -> None:
        """Sync all tasks in *plan_data* into the integrity Planner bucket."""
        bucket_id = await self._get_or_create_bucket(plan_id)
        result.buckets_synced += 1

        existing_titles = await self._get_existing_task_titles(plan_id)

        for task in plan_data.tasks:
            if task.name in existing_titles:
                logger.debug("Skipping existing task: %s", task.name)
                result.tasks_skipped += 1
                continue
            try:
                await self._create_task(
                    plan_id=plan_id,
                    bucket_id=bucket_id,
                    title=task.name,
                    description=task.description,
                    task_id=task.task_id,
                    result_text=task.result,
                )
                result.tasks_created += 1
            except (ODataError, ValueError, RuntimeError) as exc:
                msg = f"Failed to create task {task.name!r}: {exc}"
                logger.error(msg)
                result.errors.append(msg)


# ── Shared helpers ────────────────────────────────────────────────────────────


def _resolve_group_id(role: str) -> str:
    """Resolve the Microsoft 365 group ID for *role* from env vars."""
    role_key = f"PLANNER_GROUP_ID_{role.upper()}"
    group_id = os.environ.get(role_key) or os.environ.get("PLANNER_GROUP_ID")
    if not group_id:
        raise OSError(
            f"Microsoft 365 group ID not configured. "
            f"Set {role_key} or PLANNER_GROUP_ID environment variable."
        )
    return group_id
