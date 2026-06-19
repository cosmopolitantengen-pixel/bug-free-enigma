from __future__ import annotations

from app.core.models import ScheduledExecution, ScheduledJob


class SchedulerStore:
    def __init__(
        self,
        jobs: list[ScheduledJob] | None = None,
        executions: list[ScheduledExecution] | None = None,
    ) -> None:
        self._jobs: dict[str, ScheduledJob] = {job.schedule_id: job for job in jobs or []}
        self._executions: dict[str, ScheduledExecution] = {
            execution.execution_id: execution for execution in executions or []
        }

    def create(self, job: ScheduledJob) -> ScheduledJob:
        self._jobs[job.schedule_id] = job
        return job

    def get(self, schedule_id: str) -> ScheduledJob:
        return self._jobs[schedule_id]

    def list(self, status: str | None = None, action: str | None = None) -> list[ScheduledJob]:
        jobs = list(self._jobs.values())
        if status is not None:
            jobs = [job for job in jobs if job.status.value == status]
        if action is not None:
            jobs = [job for job in jobs if job.action.value == action]
        return jobs

    def record_execution(self, execution: ScheduledExecution) -> ScheduledExecution:
        self._executions[execution.execution_id] = execution
        return execution

    def list_executions(self, schedule_id: str | None = None) -> list[ScheduledExecution]:
        executions = list(self._executions.values())
        if schedule_id is not None:
            executions = [item for item in executions if item.schedule_id == schedule_id]
        return executions
