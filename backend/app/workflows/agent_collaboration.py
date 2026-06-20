from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.agents.registry import AgentRegistry
from app.audit.log import AuditLog
from app.communication.store import CommunicationStore
from app.core.enums import (
    ActionDecision,
    ApprovalStatus,
    RiskLevel,
    TaskStatus,
    WorkflowRunStatus,
    WorkflowStepStatus,
)
from app.core.models import (
    ActionRequest,
    AgentMeeting,
    AgentMessage,
    AuditEvent,
    EvaluationRecord,
    Incident,
    Task,
    TaskHandoff,
    WorkflowStep,
    WorkflowStepDefinition,
    utc_now,
)
from app.evaluations.store import EvaluationStore
from app.incidents.store import IncidentStore
from app.permissions.engine import PermissionEngine
from app.safety.risk import RiskEngine
from app.workflows.registry import WorkflowRegistry
from app.workflows.traces import WorkflowTraceStore


@dataclass(frozen=True)
class AgentCollaborationResult:
    task: Task
    output: str
    blocked: bool
    meeting: AgentMeeting | None = None
    handoff: TaskHandoff | None = None
    message: AgentMessage | None = None
    incident: Incident | None = None


class AgentCollaborationWorkflow:
    workflow_id = "agent_collaboration_v1"

    def __init__(
        self,
        workflows: WorkflowRegistry,
        agents: AgentRegistry,
        permissions: PermissionEngine,
        risks: RiskEngine,
        communication: CommunicationStore,
        audit: AuditLog,
        evaluations: EvaluationStore,
        incidents: IncidentStore,
        traces: WorkflowTraceStore,
    ) -> None:
        self.workflows = workflows
        self.agents = agents
        self.permissions = permissions
        self.risks = risks
        self.communication = communication
        self.audit = audit
        self.evaluations = evaluations
        self.incidents = incidents
        self.traces = traces
        self._skill_executor: Callable[[str, str, dict, str, str], dict] | None = None

    def set_skill_executor(self, executor: Callable[[str, str, dict, str, str], dict]) -> None:
        self._skill_executor = executor

    def validate_input(self, payload: dict[str, Any], fallback_agenda: str) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("agent collaboration input must be an object")
        target_agent_id = str(payload.get("target_agent_id", "document_agent_v1")).strip()
        if not target_agent_id:
            raise ValueError("agent collaboration target_agent_id is required")
        self.agents.get(target_agent_id)
        raw_participants = payload.get("participant_agents", [
            "workflow_agent_v1",
            "project_manager_agent_v1",
            target_agent_id,
        ])
        if not isinstance(raw_participants, list):
            raise ValueError("agent collaboration participant_agents must be an array")
        participants = list(dict.fromkeys(str(agent_id).strip() for agent_id in raw_participants if str(agent_id).strip()))
        if not participants:
            raise ValueError("agent collaboration participant_agents are required")
        if target_agent_id not in participants:
            participants.append(target_agent_id)
        for agent_id in participants:
            self.agents.get(agent_id)
        agenda = str(payload.get("agenda", fallback_agenda)).strip()
        if not agenda:
            raise ValueError("agent collaboration agenda is required")
        reason = str(payload.get("handoff_reason", "Assign the coordinated execution step.")).strip()
        if not reason:
            raise ValueError("agent collaboration handoff_reason is required")
        instructions = str(payload.get("instructions", agenda)).strip()
        if not instructions:
            raise ValueError("agent collaboration instructions are required")
        return {
            "target_agent_id": target_agent_id,
            "participant_agents": participants,
            "agenda": agenda,
            "handoff_reason": reason,
            "instructions": instructions,
        }

    def run(self, task: Task, payload: dict[str, Any]) -> AgentCollaborationResult:
        if task.status != TaskStatus.CREATED:
            raise ValueError("agent collaboration requires a newly created task")
        definition = self.workflows.get(self.workflow_id)
        if not definition.enabled:
            raise ValueError("agent collaboration workflow is disabled")
        if self._skill_executor is None:
            raise RuntimeError("agent collaboration Skill runtime is not configured")
        data = self.validate_input(payload, task.description)
        run = self.traces.start_run(self.workflow_id, task.task_id)
        task.transition(TaskStatus.IN_PROGRESS)
        meeting: AgentMeeting | None = None
        handoff: TaskHandoff | None = None
        message: AgentMessage | None = None
        collaboration_plan = ""

        for step in definition.steps:
            control_error = self._check_step_control(task, step)
            if control_error is not None:
                return self._block(task, run.run_id, step, control_error, meeting, handoff, message)
            if step.step_name == "coordinate_work":
                skill_input = {"goal": data["agenda"]}
            elif step.step_name == "prepare_handoff":
                skill_input = {
                    "goal": f"Handoff to {data['target_agent_id']}: {data['instructions']}"
                }
            elif step.step_name == "audit_collaboration":
                skill_input = {
                    "event": {
                        "event_type": "agent_collaboration_completed",
                        "task_id": task.task_id,
                        "target_agent_id": data["target_agent_id"],
                        "meeting_id": meeting.meeting_id if meeting else None,
                        "handoff_id": handoff.handoff_id if handoff else None,
                    }
                }
            else:
                return self._block(
                    task,
                    run.run_id,
                    step,
                    "unsupported collaboration step",
                    meeting,
                    handoff,
                    message,
                )
            try:
                skill_output = self._skill_executor(
                    step.skill_id,
                    step.actor_id,
                    skill_input,
                    f"{definition.name}: {step.step_name}",
                    task.task_id,
                )
            except (PermissionError, ValueError) as exc:
                return self._block(task, run.run_id, step, str(exc), meeting, handoff, message)

            if step.step_name == "coordinate_work":
                collaboration_plan = str(skill_output.get("plan", "")).strip()
                meeting = self.communication.record_meeting(
                    AgentMeeting(
                        title=f"Collaboration: {task.title}",
                        organizer_agent=step.actor_id,
                        participant_agents=data["participant_agents"],
                        agenda=data["agenda"],
                        meeting_type="workflow",
                        task_id=task.task_id,
                        minutes=collaboration_plan,
                    )
                )
                step_result = f"meeting recorded: {meeting.meeting_id}"
                output_ref = meeting.meeting_id
            elif step.step_name == "prepare_handoff":
                handoff_instructions = f"{data['instructions']}\n\nCoordination plan:\n{collaboration_plan}".strip()
                message = self.communication.send_message(
                    AgentMessage(
                        from_agent=step.actor_id,
                        to_agent=data["target_agent_id"],
                        message_type="handoff",
                        content=handoff_instructions,
                        priority="medium",
                        requires_response=True,
                        task_id=task.task_id,
                    )
                )
                handoff = self.communication.record_handoff(
                    TaskHandoff(
                        task_id=task.task_id,
                        from_agent=step.actor_id,
                        to_agent=data["target_agent_id"],
                        reason=data["handoff_reason"],
                        instructions=handoff_instructions,
                        task_status=task.status,
                        message_id=message.message_id,
                    )
                )
                step_result = f"handoff recorded: {handoff.handoff_id}"
                output_ref = handoff.handoff_id
            else:
                step_result = "collaboration audit prepared"
                output_ref = run.run_id
            self._record_step(run.run_id, task, step, WorkflowStepStatus.COMPLETED, step_result)
            self._audit_step(task, step, step_result, output_ref)

        output = f"Collaboration completed with handoff to {data['target_agent_id']}."
        task.result = output
        task.risk_level = RiskLevel.LOW
        task.transition(TaskStatus.COMPLETED)
        self.traces.complete_run(run.run_id, WorkflowRunStatus.COMPLETED, output)
        self.evaluations.write(
            EvaluationRecord(
                subject_type="workflow",
                subject_id=self.workflow_id,
                task_id=task.task_id,
                score=1.0,
                metric="agent_collaboration_completed",
                notes=output,
                risk_level=RiskLevel.LOW,
            )
        )
        self.audit.append(
            AuditEvent(
                event_type="agent_collaboration_workflow_completed",
                actor_id="workflow_agent_v1",
                action="complete_agent_collaboration",
                task_id=task.task_id,
                risk_level=RiskLevel.LOW,
                approval_status=ApprovalStatus.NOT_REQUIRED,
                result="completed",
                input_ref=meeting.meeting_id if meeting else None,
                output_ref=handoff.handoff_id if handoff else run.run_id,
            )
        )
        return AgentCollaborationResult(task, output, False, meeting, handoff, message)

    def _check_step_control(self, task: Task, step: WorkflowStepDefinition) -> str | None:
        agent = self.agents.get(step.actor_id)
        request = ActionRequest(
            action=step.action,
            actor_id=step.actor_id,
            task_id=task.task_id,
            permission_level=step.permission_level,
            reason=f"Agent Collaboration: {step.step_name}",
            target=self.workflow_id,
        )
        permission = self.permissions.evaluate(agent, request)
        risk = self.risks.assess(request)
        if permission.decision == ActionDecision.BLOCK:
            return permission.reason
        if risk.blocked:
            return "; ".join(risk.reasons)
        if permission.decision == ActionDecision.REQUIRE_APPROVAL or risk.requires_approval:
            return "collaboration step requires an approval continuation that is not available"
        return None

    def _block(
        self,
        task: Task,
        run_id: str,
        step: WorkflowStepDefinition,
        reason: str,
        meeting: AgentMeeting | None = None,
        handoff: TaskHandoff | None = None,
        message: AgentMessage | None = None,
    ) -> AgentCollaborationResult:
        task.result = reason
        task.risk_level = RiskLevel.MEDIUM
        task.transition(TaskStatus.BLOCKED)
        self._record_step(run_id, task, step, WorkflowStepStatus.BLOCKED, reason, reason, RiskLevel.MEDIUM)
        self.traces.complete_run(run_id, WorkflowRunStatus.BLOCKED, reason)
        incident = self.incidents.report(
            Incident(
                title="Agent collaboration Workflow blocked",
                description=reason,
                source_type="workflow",
                source_id=run_id,
                risk_level=RiskLevel.MEDIUM,
                task_id=task.task_id,
                actor_id=step.actor_id,
                recommendation="Review Agent permissions, Skill availability, and collaboration input before retrying.",
            )
        )
        self.audit.append(
            AuditEvent(
                event_type="agent_collaboration_workflow_blocked",
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
        return AgentCollaborationResult(task, reason, True, meeting, handoff, message, incident)

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
        output_ref: str,
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
