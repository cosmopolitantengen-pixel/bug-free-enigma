from __future__ import annotations

import re
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
from app.services.serializers import to_plain
from app.workflows.registry import WorkflowRegistry
from app.workflows.traces import WorkflowTraceStore


@dataclass(frozen=True)
class AgentMissingResult:
    task: Task
    output: str
    outcome: str
    blocked: bool
    approval_required: bool
    existing_agent: dict[str, Any] | None = None
    knowledge_matches: list[dict[str, Any]] | None = None
    proposal_plan: str | None = None
    risk_review: dict[str, Any] | None = None
    proposal: dict[str, Any] | None = None
    incident: Incident | None = None


class AgentMissingWorkflow:
    workflow_id = "agent_missing_v1"

    def __init__(
        self,
        workflows: WorkflowRegistry,
        agents: AgentRegistry,
        permissions: PermissionEngine,
        risks: RiskEngine,
        audit: AuditLog,
        evaluations: EvaluationStore,
        incidents: IncidentStore,
        traces: WorkflowTraceStore,
    ) -> None:
        self.workflows = workflows
        self.agents = agents
        self.permissions = permissions
        self.risks = risks
        self.audit = audit
        self.evaluations = evaluations
        self.incidents = incidents
        self.traces = traces
        self._skill_executor: Callable[[str, str, dict, str, str], dict[str, Any]] | None = None
        self._proposal_creator: Callable[[str, str, str, str], dict[str, Any]] | None = None

    def set_skill_executor(
        self,
        executor: Callable[[str, str, dict, str, str], dict[str, Any]],
    ) -> None:
        self._skill_executor = executor

    def set_proposal_creator(
        self,
        creator: Callable[[str, str, str, str], dict[str, Any]],
    ) -> None:
        self._proposal_creator = creator

    def validate_input(self, payload: dict[str, Any], fallback_reason: str) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("agent missing input must be an object")
        role = str(payload.get("role", "")).strip()
        department = str(payload.get("department", "")).strip()
        repeated_reason = str(payload.get("repeated_reason", fallback_reason)).strip()
        if not role:
            raise ValueError("agent missing role is required")
        if not department:
            raise ValueError("agent missing department is required")
        if not repeated_reason:
            raise ValueError("agent missing repeated_reason is required")
        allow_existing_agent = payload.get("allow_existing_agent", True)
        if not isinstance(allow_existing_agent, bool):
            raise ValueError("agent missing allow_existing_agent must be a boolean")
        knowledge_query = str(
            payload.get(
                "knowledge_query",
                f"{role} {department} {repeated_reason}",
            )
        ).strip()
        if not knowledge_query:
            raise ValueError("agent missing knowledge_query is required")
        return {
            "role": role,
            "department": department,
            "repeated_reason": repeated_reason,
            "allow_existing_agent": allow_existing_agent,
            "knowledge_query": knowledge_query,
        }

    def run(self, task: Task, payload: dict[str, Any]) -> AgentMissingResult:
        if task.status != TaskStatus.CREATED:
            raise ValueError("agent missing handling requires a newly created task")
        definition = self.workflows.get(self.workflow_id)
        if not definition.enabled:
            raise ValueError("agent missing workflow is disabled")
        if self._skill_executor is None or self._proposal_creator is None:
            raise RuntimeError("agent missing Workflow runtime is not configured")
        data = self.validate_input(payload, task.description)
        run = self.traces.start_run(self.workflow_id, task.task_id)
        task.transition(TaskStatus.WAITING_AGENT)
        detect_step, proposal_step, risk_step = definition.steps

        control_error = self._check_step_control(task, detect_step)
        if control_error:
            return self._block(task, run.run_id, detect_step, control_error)
        try:
            knowledge_output = self._execute_step(
                task,
                detect_step,
                {"query": data["knowledge_query"]},
                definition.name,
            )
        except (PermissionError, ValueError) as exc:
            return self._block(task, run.run_id, detect_step, str(exc))
        knowledge_matches = knowledge_output.get("documents", [])
        existing_agent = self._find_existing_agent(data["role"], data["department"])
        self._record_step(
            run.run_id,
            task,
            detect_step,
            WorkflowStepStatus.COMPLETED,
            f"reviewed {len(knowledge_matches)} knowledge records and the Agent registry",
        )
        self._audit_step(
            task,
            detect_step,
            "role gap detection completed",
            existing_agent.get("agent_id") if existing_agent else None,
        )
        if existing_agent is not None and data["allow_existing_agent"]:
            self._skip(run.run_id, task, proposal_step, "existing Agent can own the role")
            self._skip(run.run_id, task, risk_step, "no Agent proposal is required")
            return self._complete(
                task,
                run.run_id,
                "existing_agent",
                f"Use registered Agent: {existing_agent['agent_id']}",
                existing_agent=existing_agent,
                knowledge_matches=knowledge_matches,
            )

        control_error = self._check_step_control(task, proposal_step)
        if control_error:
            return self._block(task, run.run_id, proposal_step, control_error)
        planning_goal = (
            f"Define a constrained {data['role']} Agent in {data['department']} for this repeated need: "
            f"{data['repeated_reason']}"
        )
        try:
            planning_output = self._execute_step(
                task,
                proposal_step,
                {"goal": planning_goal},
                definition.name,
            )
        except (PermissionError, ValueError) as exc:
            return self._block(task, run.run_id, proposal_step, str(exc))
        proposal_plan = str(planning_output.get("plan", "")).strip()
        self._record_step(
            run.run_id,
            task,
            proposal_step,
            WorkflowStepStatus.COMPLETED,
            "constrained Agent proposal plan prepared",
        )
        self._audit_step(task, proposal_step, "proposal plan prepared", None)

        control_error = self._check_step_control(task, risk_step)
        if control_error:
            return self._block(task, run.run_id, risk_step, control_error)
        try:
            risk_review = self._execute_step(
                task,
                risk_step,
                {"action": "create_agent"},
                definition.name,
            )
        except (PermissionError, ValueError) as exc:
            return self._block(task, run.run_id, risk_step, str(exc))
        if risk_review.get("blocked", False):
            return self._block(task, run.run_id, risk_step, "risk Skill blocked Agent proposal creation")
        proposal = self._proposal_creator(
            data["role"],
            data["department"],
            data["repeated_reason"],
            task.task_id,
        )
        if proposal.get("status") == ProposalStatus.BLOCKED.value:
            return self._block(task, run.run_id, risk_step, "Agent proposal was blocked by approval policy")
        self._record_step(
            run.run_id,
            task,
            risk_step,
            WorkflowStepStatus.COMPLETED,
            f"risk reviewed at {risk_review.get('risk_level', RiskLevel.LOW.value)}",
        )
        self._audit_step(task, risk_step, "Agent proposal risk reviewed", proposal.get("proposal_id"))
        approval_required = proposal.get("status") == ProposalStatus.PENDING_APPROVAL.value
        return self._complete(
            task,
            run.run_id,
            "proposal",
            f"Agent proposal routed for controlled review: {proposal['proposal_id']}",
            approval_required=approval_required,
            knowledge_matches=knowledge_matches,
            proposal_plan=proposal_plan,
            risk_review=risk_review,
            proposal=proposal,
        )

    def _find_existing_agent(self, role: str, department: str) -> dict[str, Any] | None:
        tokens = [
            token
            for token in re.findall(r"[a-z0-9]+", role.lower())
            if len(token) >= 3 and token != "agent"
        ]
        if not tokens:
            return None
        department_key = department.strip().lower()
        candidates = []
        for agent in self.agents.list():
            if not agent.enabled:
                continue
            haystack = f"{agent.name} {agent.role} {agent.department}".lower()
            if all(token in haystack for token in tokens):
                candidates.append(agent)
        if not candidates:
            return None
        candidates.sort(
            key=lambda agent: (
                agent.department.lower() != department_key,
                agent.agent_id,
            )
        )
        return to_plain(candidates[0])

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
            reason=f"Agent Missing Handling: {step.step_name}",
            target=self.workflow_id,
        )
        permission = self.permissions.evaluate(agent, request)
        risk = self.risks.assess(request)
        if permission.decision == ActionDecision.BLOCK:
            return permission.reason
        if risk.blocked:
            return "; ".join(risk.reasons)
        if permission.decision == ActionDecision.REQUIRE_APPROVAL or risk.requires_approval:
            return "Agent Missing step unexpectedly requires approval before proposal routing"
        return None

    def _complete(
        self,
        task: Task,
        run_id: str,
        outcome: str,
        output: str,
        approval_required: bool = False,
        existing_agent: dict[str, Any] | None = None,
        knowledge_matches: list[dict[str, Any]] | None = None,
        proposal_plan: str | None = None,
        risk_review: dict[str, Any] | None = None,
        proposal: dict[str, Any] | None = None,
    ) -> AgentMissingResult:
        task.result = output
        task.risk_level = RiskLevel(proposal["risk_level"]) if proposal else RiskLevel.LOW
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
                metric=f"agent_missing_{outcome}",
                notes=output,
                risk_level=task.risk_level,
            )
        )
        self.audit.append(
            AuditEvent(
                event_type="agent_missing_workflow_completed",
                actor_id="agent_factory_agent_v1",
                action="resolve_agent_gap",
                task_id=task.task_id,
                risk_level=task.risk_level,
                approval_status=ApprovalStatus.PENDING if approval_required else ApprovalStatus.NOT_REQUIRED,
                result=outcome,
                output_ref=proposal.get("proposal_id") if proposal else existing_agent.get("agent_id") if existing_agent else run_id,
            )
        )
        return AgentMissingResult(
            task,
            output,
            outcome,
            False,
            approval_required,
            existing_agent,
            knowledge_matches,
            proposal_plan,
            risk_review,
            proposal,
        )

    def _block(
        self,
        task: Task,
        run_id: str,
        step: WorkflowStepDefinition,
        reason: str,
    ) -> AgentMissingResult:
        task.result = reason
        task.risk_level = RiskLevel.MEDIUM
        task.transition(TaskStatus.BLOCKED)
        self._record_step(run_id, task, step, WorkflowStepStatus.BLOCKED, reason, reason, RiskLevel.MEDIUM)
        self.traces.complete_run(run_id, WorkflowRunStatus.BLOCKED, reason)
        incident = self.incidents.report(
            Incident(
                title="Agent Missing Workflow blocked",
                description=reason,
                source_type="workflow",
                source_id=run_id,
                risk_level=RiskLevel.MEDIUM,
                task_id=task.task_id,
                actor_id=step.actor_id,
                recommendation="Review the role evidence, Agent permissions, Skill state, and proposal policy.",
            )
        )
        self.audit.append(
            AuditEvent(
                event_type="agent_missing_workflow_blocked",
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
        return AgentMissingResult(task, reason, "blocked", True, False, incident=incident)

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
                approval_status=ApprovalStatus.BLOCKED if status == WorkflowStepStatus.BLOCKED else ApprovalStatus.NOT_REQUIRED,
                result=result,
                error=error,
                completed_at=utc_now(),
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
