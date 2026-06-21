from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.audit.log import AuditLog
from app.core.enums import (
    ApprovalStatus,
    PermissionLevel,
    RiskLevel,
    TaskStatus,
    WorkflowRunStatus,
    WorkflowStepStatus,
)
from app.core.models import AuditEvent, EvaluationRecord, Incident, Task, WorkflowStep, WorkflowStepDefinition, utc_now
from app.evaluations.store import EvaluationStore
from app.incidents.store import IncidentStore
from app.workflows.registry import WorkflowRegistry
from app.workflows.traces import WorkflowTraceStore


@dataclass(frozen=True)
class GitHubProjectAnalysisResult:
    task: Task
    output: str
    outcome: str
    approval_required: bool
    blocked: bool
    approval: dict[str, Any] | None = None
    proposal: dict[str, Any] | None = None
    sandbox: dict[str, Any] | None = None
    knowledge: dict[str, Any] | None = None
    analysis: dict[str, Any] | None = None
    risk: dict[str, Any] | None = None
    incident: Incident | None = None


class GitHubProjectAnalysisWorkflow:
    workflow_id = "github_project_analysis_v1"

    def __init__(
        self,
        workflows: WorkflowRegistry,
        audit: AuditLog,
        evaluations: EvaluationStore,
        incidents: IncidentStore,
        traces: WorkflowTraceStore,
    ) -> None:
        self.workflows = workflows
        self.audit = audit
        self.evaluations = evaluations
        self.incidents = incidents
        self.traces = traces
        self._skill_executor: Callable[[str, str, dict, str, str], dict] | None = None
        self._approved_skill_executor: Callable[[str, str, dict, str, str, str], dict] | None = None
        self._approval_requester: Callable[..., dict[str, Any]] | None = None
        self._proposal_creator: Callable[..., dict[str, Any]] | None = None
        self._sandbox_runner: Callable[[str], dict[str, Any]] | None = None
        self._proposal_registrar: Callable[[str], dict[str, Any]] | None = None

    def set_skill_executor(self, executor: Callable[[str, str, dict, str, str], dict]) -> None:
        self._skill_executor = executor

    def set_approved_skill_executor(
        self,
        executor: Callable[[str, str, dict, str, str, str], dict],
    ) -> None:
        self._approved_skill_executor = executor

    def set_approval_requester(self, requester: Callable[..., dict[str, Any]]) -> None:
        self._approval_requester = requester

    def set_proposal_creator(self, creator: Callable[..., dict[str, Any]]) -> None:
        self._proposal_creator = creator

    def set_sandbox_runner(self, runner: Callable[[str], dict[str, Any]]) -> None:
        self._sandbox_runner = runner

    def set_proposal_registrar(self, registrar: Callable[[str], dict[str, Any]]) -> None:
        self._proposal_registrar = registrar

    def validate_input(self, payload: dict[str, Any]) -> dict[str, str]:
        if not isinstance(payload, dict):
            raise ValueError("GitHub project analysis input must be an object")
        data = {
            "repo_url": str(payload.get("repo_url", "")).strip(),
            "requested_by_agent": str(payload.get("requested_by_agent", "ceo_agent_v1")).strip(),
            "readme": str(payload.get("readme", "")).strip(),
            "license_name": str(payload.get("license_name", "unknown")).strip() or "unknown",
            "maintenance_signal": str(payload.get("maintenance_signal", "unknown")).strip() or "unknown",
        }
        if not data["repo_url"]:
            raise ValueError("GitHub project analysis repo_url is required")
        if not data["readme"]:
            raise ValueError("GitHub project analysis readme is required")
        if not data["requested_by_agent"]:
            raise ValueError("GitHub project analysis requested_by_agent is required")
        return data

    def run(self, task: Task, payload: dict[str, Any]) -> GitHubProjectAnalysisResult:
        if task.status != TaskStatus.CREATED:
            raise ValueError("GitHub project analysis requires a newly created task")
        definition = self.workflows.get(self.workflow_id)
        if not definition.enabled:
            raise ValueError("GitHub project analysis workflow is disabled")
        self._ensure_runtime()
        data = self.validate_input(payload)
        run = self.traces.start_run(self.workflow_id, task.task_id)
        first_step = definition.steps[0]
        try:
            requested = self._approval_requester(
                action="analyze_github_repository",
                actor_id=data["requested_by_agent"],
                permission_level=PermissionLevel.L3_EXTERNAL_PREPARE,
                reason=f"Analyze supplied GitHub repository material: {data['repo_url']}",
                task_id=task.task_id,
                target=data["repo_url"],
                possible_benefit="Assess reusable open-source ideas and register safe findings as internal Knowledge.",
                possible_loss="Untrusted, incompatible, or malicious repository material could influence system behavior.",
                metadata={
                    "workflow_id": self.workflow_id,
                    "approved_skill_ids": ["github_project_analysis_skill_v1"],
                    "workflow_input": data,
                },
            )
        except (KeyError, PermissionError, ValueError) as exc:
            return self._block(task, run.run_id, first_step, str(exc))

        approval = requested.get("approval")
        risk = requested.get("risk", {})
        if not approval or approval.get("status") == ApprovalStatus.BLOCKED.value:
            reason = requested.get("permission_reason") or "GitHub analysis approval was blocked"
            return self._block(task, run.run_id, first_step, reason, RiskLevel(risk.get("level", "medium")))

        task.approval_id = approval["approval_id"]
        task.risk_level = RiskLevel(risk.get("level", RiskLevel.MEDIUM.value))
        task.result = "GitHub project analysis requires Human Root approval."
        task.transition(TaskStatus.NEEDS_APPROVAL)
        self._record_step(
            run.run_id,
            task,
            first_step,
            WorkflowStepStatus.WAITING_APPROVAL,
            "repository analysis is waiting for Human Root approval",
            task.risk_level,
            ApprovalStatus.PENDING,
        )
        self.traces.complete_run(run.run_id, WorkflowRunStatus.WAITING_APPROVAL, task.result)
        self.audit.append(
            AuditEvent(
                event_type="github_analysis_workflow_waiting_approval",
                actor_id=data["requested_by_agent"],
                action="analyze_github_repository",
                task_id=task.task_id,
                risk_level=task.risk_level,
                approval_status=ApprovalStatus.PENDING,
                result="waiting_approval",
                input_ref=data["repo_url"],
                output_ref=task.approval_id,
            )
        )
        return GitHubProjectAnalysisResult(
            task,
            task.result,
            "waiting_approval",
            True,
            False,
            approval=approval,
            risk=risk,
        )

    def resume_after_decision(self, task: Task, approval: dict[str, Any]) -> GitHubProjectAnalysisResult:
        if task.status != TaskStatus.NEEDS_APPROVAL:
            raise ValueError("task is not waiting for GitHub project analysis approval")
        run = self.traces.latest_run_for_task(task.task_id, self.workflow_id)
        if run is None or run.status != WorkflowRunStatus.WAITING_APPROVAL:
            raise ValueError("task has no waiting GitHub project analysis Workflow run")
        if not task.approval_id or approval.get("approval_id") != task.approval_id:
            raise ValueError("GitHub project analysis approval does not match task")
        status = ApprovalStatus(approval["status"])
        definition = self.workflows.get(self.workflow_id)
        if status in {ApprovalStatus.PENDING, ApprovalStatus.NEED_MORE_INFO}:
            raise ValueError("GitHub project analysis approval has no final decision")
        if status == ApprovalStatus.REJECTED:
            return self._reject(task, run.run_id, definition.steps, approval)
        if status != ApprovalStatus.APPROVED:
            return self._block(
                task,
                run.run_id,
                definition.steps[0],
                f"GitHub project analysis approval is {status.value}",
                task.risk_level,
                approval,
            )

        metadata = approval.get("request", {}).get("metadata", {})
        if metadata.get("workflow_id") != self.workflow_id:
            raise ValueError("approval is not scoped to GitHub project analysis Workflow")
        data = self.validate_input(metadata.get("workflow_input", {}))
        task.transition(TaskStatus.APPROVED)
        task.transition(TaskStatus.EXECUTING)
        analysis_step, risk_step, curate_step = definition.steps

        try:
            analysis = self._approved_skill_executor(
                analysis_step.skill_id,
                analysis_step.actor_id,
                {
                    "repository": data["repo_url"],
                    "metadata": {
                        "readme": data["readme"],
                        "license_name": data["license_name"],
                        "maintenance_signal": data["maintenance_signal"],
                        "content_trust": "external_untrusted",
                    },
                },
                f"{definition.name}: {analysis_step.step_name}",
                task.task_id,
                task.approval_id,
            )
        except (KeyError, PermissionError, ValueError) as exc:
            return self._block(task, run.run_id, analysis_step, str(exc), task.risk_level, approval)
        self._record_step(
            run.run_id,
            task,
            analysis_step,
            WorkflowStepStatus.COMPLETED,
            "untrusted repository metadata analyzed",
            RiskLevel.MEDIUM,
            ApprovalStatus.APPROVED,
        )
        self._audit_step(task, analysis_step, "analysis completed", task.approval_id)

        try:
            risk = self._skill_executor(
                risk_step.skill_id,
                risk_step.actor_id,
                {"action": "prepare_external_content"},
                f"{definition.name}: {risk_step.step_name}",
                task.task_id,
            )
        except (KeyError, PermissionError, ValueError) as exc:
            return self._block(task, run.run_id, risk_step, str(exc), RiskLevel.MEDIUM, approval)
        if risk.get("blocked", False):
            return self._block(task, run.run_id, risk_step, "risk Skill blocked repository analysis", RiskLevel.FORBIDDEN, approval)
        self._record_step(
            run.run_id,
            task,
            risk_step,
            WorkflowStepStatus.COMPLETED,
            f"repository review risk: {risk.get('risk_level', 'medium')}",
            RiskLevel(risk.get("risk_level", RiskLevel.MEDIUM.value)),
            ApprovalStatus.APPROVED,
        )
        self._audit_step(task, risk_step, "risk review completed", task.approval_id)

        try:
            proposal = self._proposal_creator(
                repo_url=data["repo_url"],
                requested_by_agent=data["requested_by_agent"],
                readme=data["readme"],
                license_name=data["license_name"],
                maintenance_signal=data["maintenance_signal"],
                task_id=task.task_id,
                approval_id=task.approval_id,
            )
            curated = self._approved_skill_executor(
                curate_step.skill_id,
                curate_step.actor_id,
                {
                    "repository": data["repo_url"],
                    "metadata": {
                        "summary": proposal["summary"],
                        "recommended_capabilities": proposal["recommended_capabilities"],
                        "external_content_findings": proposal["external_content_findings"],
                        "security_findings": proposal["security_findings"],
                        "risk_level": proposal["risk_level"],
                    },
                },
                f"{definition.name}: {curate_step.step_name}",
                task.task_id,
                task.approval_id,
            )
            sandbox = self._sandbox_runner(proposal["proposal_id"])
        except (KeyError, PermissionError, ValueError) as exc:
            return self._block(task, run.run_id, curate_step, str(exc), RiskLevel.MEDIUM, approval)

        if sandbox.get("sandbox_status") != "passed":
            return self._block(
                task,
                run.run_id,
                curate_step,
                sandbox.get("sandbox_notes") or "GitHub absorption sandbox failed",
                RiskLevel(sandbox.get("risk_level", RiskLevel.HIGH.value)),
                approval,
                proposal,
                sandbox,
            )
        try:
            registered = self._proposal_registrar(proposal["proposal_id"])
        except (KeyError, PermissionError, ValueError) as exc:
            return self._block(task, run.run_id, curate_step, str(exc), RiskLevel.MEDIUM, approval, proposal, sandbox)
        knowledge = registered["knowledge"]
        proposal = registered["proposal"]
        self._record_step(
            run.run_id,
            task,
            curate_step,
            WorkflowStepStatus.COMPLETED,
            f"safe analysis registered as Knowledge: {knowledge['doc_id']}",
            RiskLevel(proposal["risk_level"]),
            ApprovalStatus.APPROVED,
        )
        self._audit_step(task, curate_step, "knowledge registered", knowledge["doc_id"])
        return self._complete(task, run.run_id, approval, proposal, sandbox, knowledge, analysis, curated, risk)

    def _complete(
        self,
        task: Task,
        run_id: str,
        approval: dict[str, Any],
        proposal: dict[str, Any],
        sandbox: dict[str, Any],
        knowledge: dict[str, Any],
        analysis: dict[str, Any],
        curated: dict[str, Any],
        risk: dict[str, Any],
    ) -> GitHubProjectAnalysisResult:
        output = f"GitHub project analysis registered safe Knowledge: {knowledge['doc_id']}"
        task.result = output
        task.risk_level = RiskLevel(proposal["risk_level"])
        task.transition(TaskStatus.COMPLETED)
        self.traces.complete_run(run_id, WorkflowRunStatus.COMPLETED, output)
        self.evaluations.write(
            EvaluationRecord(
                subject_type="workflow",
                subject_id=self.workflow_id,
                task_id=task.task_id,
                score=1.0,
                metric="github_project_analysis_registered",
                notes=output,
                risk_level=task.risk_level,
            )
        )
        self.audit.append(
            AuditEvent(
                event_type="github_analysis_workflow_completed",
                actor_id="workflow_engine",
                action="complete_github_project_analysis",
                task_id=task.task_id,
                risk_level=task.risk_level,
                approval_status=ApprovalStatus.APPROVED,
                result="registered_knowledge",
                input_ref=proposal["proposal_id"],
                output_ref=knowledge["doc_id"],
            )
        )
        return GitHubProjectAnalysisResult(
            task,
            output,
            "registered_knowledge",
            False,
            False,
            approval=approval,
            proposal=proposal,
            sandbox=sandbox,
            knowledge=knowledge,
            analysis={"initial": analysis, "curated": curated},
            risk=risk,
        )

    def _reject(
        self,
        task: Task,
        run_id: str,
        steps: tuple[WorkflowStepDefinition, ...],
        approval: dict[str, Any],
    ) -> GitHubProjectAnalysisResult:
        for step in steps:
            self._record_step(
                run_id,
                task,
                step,
                WorkflowStepStatus.SKIPPED,
                "Human Root rejected repository analysis",
                task.risk_level,
                ApprovalStatus.REJECTED,
            )
        output = "Human Root rejected GitHub project analysis."
        task.result = output
        task.transition(TaskStatus.CANCELLED)
        self.traces.complete_run(run_id, WorkflowRunStatus.COMPLETED, output)
        self.evaluations.write(
            EvaluationRecord(
                subject_type="workflow",
                subject_id=self.workflow_id,
                task_id=task.task_id,
                score=1.0,
                metric="github_project_analysis_rejected_enforced",
                notes=output,
                risk_level=task.risk_level,
            )
        )
        self.audit.append(
            AuditEvent(
                event_type="github_analysis_workflow_rejected",
                actor_id="human_root",
                action="reject_github_project_analysis",
                task_id=task.task_id,
                risk_level=task.risk_level,
                approval_status=ApprovalStatus.REJECTED,
                result="cancelled",
                output_ref=approval["approval_id"],
            )
        )
        return GitHubProjectAnalysisResult(task, output, "rejected", False, False, approval=approval)

    def _block(
        self,
        task: Task,
        run_id: str,
        step: WorkflowStepDefinition,
        reason: str,
        risk_level: RiskLevel = RiskLevel.MEDIUM,
        approval: dict[str, Any] | None = None,
        proposal: dict[str, Any] | None = None,
        sandbox: dict[str, Any] | None = None,
    ) -> GitHubProjectAnalysisResult:
        task.result = reason
        task.risk_level = risk_level
        task.transition(TaskStatus.BLOCKED)
        approval_status = ApprovalStatus(approval["status"]) if approval else ApprovalStatus.BLOCKED
        self._record_step(
            run_id,
            task,
            step,
            WorkflowStepStatus.BLOCKED,
            reason,
            risk_level,
            approval_status,
            reason,
        )
        self.traces.complete_run(run_id, WorkflowRunStatus.BLOCKED, reason)
        incident = self.incidents.report(
            Incident(
                title="GitHub Project Analysis Workflow blocked",
                description=reason,
                source_type="workflow",
                source_id=run_id,
                risk_level=risk_level,
                task_id=task.task_id,
                actor_id=step.actor_id,
                recommendation="Review approval scope, repository license/security findings, Skill controls, and sandbox evidence.",
            )
        )
        self.audit.append(
            AuditEvent(
                event_type="github_analysis_workflow_blocked",
                actor_id=step.actor_id,
                action=step.action,
                task_id=task.task_id,
                risk_level=risk_level,
                approval_status=approval_status,
                result=reason,
                output_ref=incident.incident_id,
                error=reason,
            )
        )
        return GitHubProjectAnalysisResult(
            task,
            reason,
            "blocked",
            False,
            True,
            approval=approval,
            proposal=proposal,
            sandbox=sandbox,
            incident=incident,
        )

    def _record_step(
        self,
        run_id: str,
        task: Task,
        step: WorkflowStepDefinition,
        status: WorkflowStepStatus,
        result: str,
        risk_level: RiskLevel,
        approval_status: ApprovalStatus,
        error: str | None = None,
    ) -> None:
        self.traces.append_step(
            WorkflowStep(
                run_id=run_id,
                task_id=task.task_id,
                sequence=step.sequence,
                step_name=step.step_name,
                actor_id=step.actor_id,
                action=step.action,
                status=status,
                risk_level=risk_level,
                approval_status=approval_status,
                result=result,
                error=error,
                completed_at=None if status == WorkflowStepStatus.WAITING_APPROVAL else utc_now(),
            )
        )

    def _audit_step(self, task: Task, step: WorkflowStepDefinition, result: str, output_ref: str | None) -> None:
        self.audit.append(
            AuditEvent(
                event_type="workflow_step_recorded",
                actor_id=step.actor_id,
                action=step.action,
                task_id=task.task_id,
                risk_level=task.risk_level,
                approval_status=ApprovalStatus.APPROVED,
                result=result,
                input_ref=self.workflow_id,
                output_ref=output_ref,
            )
        )

    def _ensure_runtime(self) -> None:
        if any(
            dependency is None
            for dependency in (
                self._skill_executor,
                self._approved_skill_executor,
                self._approval_requester,
                self._proposal_creator,
                self._sandbox_runner,
                self._proposal_registrar,
            )
        ):
            raise RuntimeError("GitHub Project Analysis Workflow runtime is not configured")
