from __future__ import annotations

from app.core.enums import WorkflowRunStatus
from app.core.models import WorkflowRun, WorkflowStep, utc_now


class WorkflowTraceStore:
    def __init__(self, runs: list[WorkflowRun] | None = None, steps: list[WorkflowStep] | None = None) -> None:
        self._runs: dict[str, WorkflowRun] = {run.run_id: run for run in runs or []}
        self._steps: list[WorkflowStep] = list(steps or [])

    def start_run(self, workflow_id: str, task_id: str) -> WorkflowRun:
        run = WorkflowRun(workflow_id=workflow_id, task_id=task_id)
        self._runs[run.run_id] = run
        return run

    def append_step(self, step: WorkflowStep) -> WorkflowStep:
        self._steps.append(step)
        return step

    def complete_run(self, run_id: str, status: WorkflowRunStatus, result: str | None = None) -> WorkflowRun:
        run = self._runs[run_id]
        run.status = status
        run.result = result
        run.completed_at = utc_now()
        return run

    def list_runs(self) -> list[WorkflowRun]:
        return list(self._runs.values())

    def latest_run_for_task(self, task_id: str, workflow_id: str | None = None) -> WorkflowRun | None:
        runs = [run for run in self._runs.values() if run.task_id == task_id]
        if workflow_id is not None:
            runs = [run for run in runs if run.workflow_id == workflow_id]
        return runs[-1] if runs else None

    def list_steps(self, run_id: str | None = None) -> list[WorkflowStep]:
        if run_id is None:
            return list(self._steps)
        return [step for step in self._steps if step.run_id == run_id]
