from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from app.agents.registry import AgentRegistry
from app.audit.log import AuditLog
from app.core.enums import (
    ActionDecision,
    ApprovalStatus,
    ProposalStatus,
    RiskLevel,
    TaskStatus,
    WorkflowRunStatus,
    WorkflowStepStatus,
)
from app.core.models import (
    ActionRequest,
    AuditEvent,
    EvaluationRecord,
    Incident,
    Task,
    WorkflowStep,
    WorkflowStepDefinition,
    utc_now,
)
from app.evaluations.store import EvaluationStore
from app.incidents.store import IncidentStore
from app.permissions.engine import PermissionEngine
from app.safety.risk import RiskEngine
from app.skills.registry import SkillRegistry
from app.workflows.registry import WorkflowRegistry
from app.workflows.traces import WorkflowTraceStore


@dataclass(frozen=True)
class SkillMissingResult:
    task: Task
    output: str
    outcome: str
    blocked: bool
    approval_required: bool
    replacement: dict[str, Any] | None = None
    composition: dict[str, Any] | None = None
    temporary_skill: dict[str, Any] | None = None
    proposal: dict[str, Any] | None = None
    incident: Incident | None = None


class SkillMissingWorkflow:
    workflow_id = "skill_missing_v1"

    def __init__(
        self,
        workflows: WorkflowRegistry,
        agents: AgentRegistry,
        skills: SkillRegistry,
        permissions: PermissionEngine,
        risks: RiskEngine,
        audit: AuditLog,
        evaluations: EvaluationStore,
        incidents: IncidentStore,
        traces: WorkflowTraceStore,
    ) -> None:
        self.workflows = workflows
        self.agents = agents
        self.skills = skills
        self.permissions = permissions
        self.risks = risks
        self.audit = audit
        self.evaluations = evaluations
        self.incidents = incidents
        self.traces = traces
        self._skill_executor: Callable[[str, str, dict, str, str], dict] | None = None
        self._skill_requester: Callable[[str, str, dict, str, str], dict[str, Any]] | None = None
        self._skill_continuation: Callable[[str, str], dict[str, Any]] | None = None
        self._proposal_creator: Callable[[str, str, RiskLevel], dict[str, Any]] | None = None

    def set_skill_executor(self, executor: Callable[[str, str, dict, str, str], dict]) -> None:
        self._skill_executor = executor

    def set_skill_requester(
        self,
        requester: Callable[[str, str, dict, str, str], dict[str, Any]],
    ) -> None:
        self._skill_requester = requester

    def set_skill_continuation(
        self,
        continuation: Callable[[str, str], dict[str, Any]],
    ) -> None:
        self._skill_continuation = continuation

    def set_proposal_creator(
        self,
        creator: Callable[[str, str, RiskLevel], dict[str, Any]],
    ) -> None:
        self._proposal_creator = creator

    def validate_input(self, payload: dict[str, Any], fallback_capability: str) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("skill missing input must be an object")
        capability = str(payload.get("capability", fallback_capability)).strip()
        if not capability:
            raise ValueError("skill missing capability is required")
        requested_by_agent = str(payload.get("requested_by_agent", "document_agent_v1")).strip()
        if not requested_by_agent:
            raise ValueError("skill missing requested_by_agent is required")
        self.agents.get(requested_by_agent)
        raw_candidates = payload.get("candidate_skill_ids", [])
        if not isinstance(raw_candidates, list):
            raise ValueError("skill missing candidate_skill_ids must be an array")
        candidate_skill_ids = list(
            dict.fromkeys(str(skill_id).strip() for skill_id in raw_candidates if str(skill_id).strip())
        )
        for skill_id in candidate_skill_ids:
            skill = self.skills.get(skill_id)
            if not skill.enabled or requested_by_agent not in skill.allowed_agents:
                raise ValueError(
                    f"candidate Skill is not enabled and authorized for {requested_by_agent}: {skill_id}"
                )
        raw_constraints = payload.get("constraints", [])
        if not isinstance(raw_constraints, list):
            raise ValueError("skill missing constraints must be an array")
        constraints = [str(value).strip() for value in raw_constraints if str(value).strip()]
        try:
            risk_level = RiskLevel(payload.get("risk_level", RiskLevel.MEDIUM.value))
        except ValueError as exc:
            raise ValueError("skill missing risk_level is invalid") from exc
        allow_replacement = payload.get("allow_replacement", True)
        if not isinstance(allow_replacement, bool):
            raise ValueError("skill missing allow_replacement must be a boolean")
        return {
            "capability": capability,
            "requested_by_agent": requested_by_agent,
            "candidate_skill_ids": candidate_skill_ids,
            "constraints": constraints,
            "risk_level": risk_level,
            "allow_replacement": allow_replacement,
        }

    def run(self, task: Task, payload: dict[str, Any]) -> SkillMissingResult:
        if task.status != TaskStatus.CREATED:
            raise ValueError("skill missing handling requires a newly created task")
        definition = self.workflows.get(self.workflow_id)
        if not definition.enabled:
            raise ValueError("skill missing workflow is disabled")
        if (
            self._skill_executor is None
            or self._skill_requester is None
            or self._skill_continuation is None
            or self._proposal_creator is None
        ):
            raise RuntimeError("skill missing Workflow runtime is not configured")
        data = self.validate_input(payload, task.description)
        run = self.traces.start_run(self.workflow_id, task.task_id)
        task.transition(TaskStatus.WAITING_SKILL)
        search_step, composition_step, proposal_step = definition.steps

        control_error = self._check_step_control(task, search_step)
        if control_error:
            return self._block(task, run.run_id, search_step, control_error)
        try:
            search_output = self._execute_step(
                task,
                search_step,
                {"query": data["capability"]},
                definition.name,
            )
        except (PermissionError, ValueError) as exc:
            return self._block(task, run.run_id, search_step, str(exc))
        matches = [
            skill
            for skill in search_output.get("skills", [])
            if skill.get("enabled", False)
            and data["requested_by_agent"] in skill.get("allowed_agents", [])
        ]
        replacement = matches[0] if matches and data["allow_replacement"] else None
        self._record_step(
            run.run_id,
            task,
            search_step,
            WorkflowStepStatus.COMPLETED,
            f"found {len(matches)} authorized candidate Skills",
        )
        self._audit_step(task, search_step, "search completed", replacement.get("skill_id") if replacement else None)
        if replacement is not None:
            self._skip(run.run_id, task, composition_step, "replacement Skill found")
            self._skip(run.run_id, task, proposal_step, "replacement Skill found")
            return self._complete(
                task,
                run.run_id,
                "replacement",
                f"Use registered replacement Skill: {replacement['skill_id']}",
                replacement=replacement,
            )

        control_error = self._check_step_control(task, composition_step)
        if control_error:
            return self._block(task, run.run_id, composition_step, control_error)
        candidate_ids = data["candidate_skill_ids"] or [skill["skill_id"] for skill in matches]
        try:
            composition_output = self._execute_step(
                task,
                composition_step,
                {"goal": data["capability"], "skill_ids": candidate_ids},
                definition.name,
            )
        except (PermissionError, ValueError) as exc:
            return self._block(task, run.run_id, composition_step, str(exc))
        composition = composition_output.get("composition", {})
        composed_steps = composition.get("steps", [])
        self._record_step(
            run.run_id,
            task,
            composition_step,
            WorkflowStepStatus.COMPLETED,
            f"composition contains {len(composed_steps)} Skill steps",
        )
        self._audit_step(task, composition_step, "composition evaluated", ",".join(candidate_ids) or None)
        if len(composed_steps) >= 2:
            self._skip(run.run_id, task, proposal_step, "existing Skill composition is sufficient")
            return self._complete(
                task,
                run.run_id,
                "composition",
                "Use the validated composition of registered Skills.",
                composition=composition,
            )

        control_error = self._check_step_control(task, proposal_step)
        if control_error:
            return self._block(task, run.run_id, proposal_step, control_error)
        skill_input = {
            "capability": data["capability"],
            "constraints": data["constraints"],
            "requested_by_agent": data["requested_by_agent"],
            "requested_risk_level": data["risk_level"].value,
        }
        try:
            requested = self._skill_requester(
                proposal_step.skill_id,
                proposal_step.actor_id,
                skill_input,
                f"{definition.name}: {proposal_step.step_name}",
                task.task_id,
            )
        except (PermissionError, ValueError) as exc:
            return self._block(task, run.run_id, proposal_step, str(exc))
        skill_run = requested["run"]
        if skill_run["status"] == "waiting_approval":
            return self._wait_for_skill_approval(task, run.run_id, proposal_step, skill_run)
        if skill_run["status"] != "completed":
            return self._block(
                task,
                run.run_id,
                proposal_step,
                skill_run.get("error") or f"temporary Skill run entered {skill_run['status']}",
            )
        try:
            temporary_output = json.loads(skill_run["result"])
        except (TypeError, json.JSONDecodeError) as exc:
            return self._block(task, run.run_id, proposal_step, f"invalid temporary Skill output: {exc}")
        return self._route_proposal(task, run.run_id, proposal_step, data, temporary_output)

    def resume_after_approval(self, task: Task) -> SkillMissingResult:
        if task.status != TaskStatus.NEEDS_APPROVAL:
            raise ValueError("task is not waiting for Skill Missing Workflow approval")
        run = self.traces.latest_run_for_task(task.task_id, self.workflow_id)
        if run is None or run.status != WorkflowRunStatus.WAITING_APPROVAL:
            raise ValueError("task has no waiting Skill Missing Workflow run")
        definition = self.workflows.get(self.workflow_id)
        proposal_step = definition.steps[2]
        try:
            continued = self._skill_continuation(task.task_id, proposal_step.skill_id)
        except (KeyError, PermissionError, ValueError) as exc:
            raise ValueError(str(exc)) from exc
        skill_run = continued["run"]
        if skill_run["status"] != "completed":
            return self._block(
                task,
                run.run_id,
                proposal_step,
                skill_run.get("error") or f"temporary Skill run entered {skill_run['status']}",
            )
        try:
            temporary_output = json.loads(skill_run["result"])
        except (TypeError, json.JSONDecodeError) as exc:
            return self._block(task, run.run_id, proposal_step, f"invalid temporary Skill output: {exc}")
        skill_input = skill_run["input"]
        data = {
            "capability": skill_input["capability"],
            "requested_by_agent": skill_input["requested_by_agent"],
            "risk_level": RiskLevel(skill_input["requested_risk_level"]),
        }
        task.transition(TaskStatus.WAITING_SKILL)
        return self._route_proposal(task, run.run_id, proposal_step, data, temporary_output)

    def _route_proposal(
        self,
        task: Task,
        run_id: str,
        proposal_step: WorkflowStepDefinition,
        data: dict[str, Any],
        temporary_output: dict[str, Any],
    ) -> SkillMissingResult:
        temporary_skill = temporary_output.get("skill_proposal", {})
        proposal = self._proposal_creator(
            data["capability"],
            data["requested_by_agent"],
            data["risk_level"],
        )
        if proposal.get("status") == ProposalStatus.BLOCKED.value:
            return self._block(
                task,
                run_id,
                proposal_step,
                "Skill proposal was blocked by approval policy",
            )
        self._record_step(
            run_id,
            task,
            proposal_step,
            WorkflowStepStatus.COMPLETED,
            f"temporary Skill definition prepared: {temporary_skill.get('skill_id', 'unknown')}",
        )
        self._audit_step(task, proposal_step, "formal proposal routed", proposal.get("proposal_id"))
        approval_required = proposal.get("status") == ProposalStatus.PENDING_APPROVAL.value
        return self._complete(
            task,
            run_id,
            "proposal",
            f"Skill proposal routed for controlled review: {proposal['proposal_id']}",
            approval_required=approval_required,
            temporary_skill=temporary_skill,
            proposal=proposal,
        )

    def _wait_for_skill_approval(
        self,
        task: Task,
        run_id: str,
        step: WorkflowStepDefinition,
        skill_run: dict[str, Any],
    ) -> SkillMissingResult:
        task.result = "Temporary Skill preparation requires Human Root approval."
        task.risk_level = RiskLevel(skill_run["risk_level"])
        task.approval_id = skill_run["approval_id"]
        task.transition(TaskStatus.NEEDS_APPROVAL)
        self._record_step(
            run_id,
            task,
            step,
            WorkflowStepStatus.WAITING_APPROVAL,
            f"Skill Run waiting for approval: {skill_run['run_id']}",
            approval_status=ApprovalStatus.PENDING,
        )
        self.traces.complete_run(run_id, WorkflowRunStatus.WAITING_APPROVAL, task.result)
        self.audit.append(
            AuditEvent(
                event_type="skill_missing_workflow_waiting_approval",
                actor_id=step.actor_id,
                action=step.action,
                task_id=task.task_id,
                risk_level=task.risk_level,
                approval_status=ApprovalStatus.PENDING,
                result="waiting_approval",
                input_ref=skill_run["run_id"],
                output_ref=skill_run["approval_id"],
            )
        )
        return SkillMissingResult(
            task,
            task.result,
            "skill_approval",
            False,
            True,
        )

    def _execute_step(
        self,
        task: Task,
        step: WorkflowStepDefinition,
        skill_input: dict[str, Any],
        workflow_name: str,
    ) -> dict[str, Any]:
        return self._skill_executor(
            step.skill_id,
            step.actor_id,
            skill_input,
            f"{workflow_name}: {step.step_name}",
            task.task_id,
        )

    def _check_step_control(self, task: Task, step: WorkflowStepDefinition) -> str | None:
        agent = self.agents.get(step.actor_id)
        request = ActionRequest(
            action=step.action,
            actor_id=step.actor_id,
            task_id=task.task_id,
            permission_level=step.permission_level,
            reason=f"Skill Missing Handling: {step.step_name}",
            target=self.workflow_id,
        )
        permission = self.permissions.evaluate(agent, request)
        risk = self.risks.assess(request)
        if permission.decision == ActionDecision.BLOCK:
            return permission.reason
        if risk.blocked:
            return "; ".join(risk.reasons)
        if permission.decision == ActionDecision.REQUIRE_APPROVAL or risk.requires_approval:
            return "Skill Missing step unexpectedly requires approval before proposal creation"
        return None

    def _complete(
        self,
        task: Task,
        run_id: str,
        outcome: str,
        output: str,
        approval_required: bool = False,
        replacement: dict[str, Any] | None = None,
        composition: dict[str, Any] | None = None,
        temporary_skill: dict[str, Any] | None = None,
        proposal: dict[str, Any] | None = None,
    ) -> SkillMissingResult:
        task.result = output
        task.risk_level = (
            RiskLevel(proposal.get("risk_level", RiskLevel.MEDIUM.value))
            if proposal
            else RiskLevel.LOW
        )
        if approval_required and proposal:
            task.approval_id = proposal.get("approval_id")
        task.transition(TaskStatus.NEEDS_APPROVAL if approval_required else TaskStatus.COMPLETED)
        self.traces.complete_run(run_id, WorkflowRunStatus.COMPLETED, output)
        self.evaluations.write(
            EvaluationRecord(
                subject_type="workflow",
                subject_id=self.workflow_id,
                task_id=task.task_id,
                score=1.0,
                metric=f"skill_missing_{outcome}",
                notes=output,
                risk_level=task.risk_level,
            )
        )
        self.audit.append(
            AuditEvent(
                event_type="skill_missing_workflow_completed",
                actor_id="skill_manager_agent_v1",
                action="resolve_skill_gap",
                task_id=task.task_id,
                risk_level=task.risk_level,
                approval_status=ApprovalStatus.PENDING if approval_required else ApprovalStatus.NOT_REQUIRED,
                result=outcome,
                output_ref=proposal.get("proposal_id") if proposal else replacement.get("skill_id") if replacement else run_id,
            )
        )
        return SkillMissingResult(
            task,
            output,
            outcome,
            False,
            approval_required,
            replacement,
            composition,
            temporary_skill,
            proposal,
        )

    def _block(
        self,
        task: Task,
        run_id: str,
        step: WorkflowStepDefinition,
        reason: str,
    ) -> SkillMissingResult:
        task.result = reason
        task.risk_level = RiskLevel.MEDIUM
        task.transition(TaskStatus.BLOCKED)
        self._record_step(run_id, task, step, WorkflowStepStatus.BLOCKED, reason, reason, RiskLevel.MEDIUM)
        self.traces.complete_run(run_id, WorkflowRunStatus.BLOCKED, reason)
        incident = self.incidents.report(
            Incident(
                title="Skill Missing Workflow blocked",
                description=reason,
                source_type="workflow",
                source_id=run_id,
                risk_level=RiskLevel.MEDIUM,
                task_id=task.task_id,
                actor_id=step.actor_id,
                recommendation="Review requested capability, Agent authorization, Skill state, and proposal policy.",
            )
        )
        self.audit.append(
            AuditEvent(
                event_type="skill_missing_workflow_blocked",
                actor_id=step.actor_id,
                action=step.action,
                task_id=task.task_id,
                risk_level=RiskLevel.MEDIUM,
                approval_status=ApprovalStatus.BLOCKED,
                result=reason,
                output_ref=incident.incident_id,
                error=reason,
            )
        )
        return SkillMissingResult(task, reason, "blocked", True, False, incident=incident)

    def _skip(self, run_id: str, task: Task, step: WorkflowStepDefinition, reason: str) -> None:
        self._record_step(run_id, task, step, WorkflowStepStatus.SKIPPED, reason)
        self._audit_step(task, step, reason, None)

    def _record_step(
        self,
        run_id: str,
        task: Task,
        step: WorkflowStepDefinition,
        status: WorkflowStepStatus,
        result: str,
        error: str | None = None,
        risk_level: RiskLevel = RiskLevel.LOW,
        approval_status: ApprovalStatus | None = None,
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
                approval_status=approval_status
                or (ApprovalStatus.BLOCKED if status == WorkflowStepStatus.BLOCKED else ApprovalStatus.NOT_REQUIRED),
                result=result,
                error=error,
                completed_at=None if status == WorkflowStepStatus.WAITING_APPROVAL else utc_now(),
            )
        )

    def _audit_step(
        self,
        task: Task,
        step: WorkflowStepDefinition,
        result: str,
        output_ref: str | None,
    ) -> None:
        self.audit.append(
            AuditEvent(
                event_type="workflow_step_recorded",
                actor_id=step.actor_id,
                action=step.action,
                task_id=task.task_id,
                risk_level=RiskLevel.LOW,
                approval_status=ApprovalStatus.NOT_REQUIRED,
                result=result,
                input_ref=self.workflow_id,
                output_ref=output_ref,
            )
        )
