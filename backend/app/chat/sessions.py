from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from threading import RLock
from typing import Any

from app.core.models import new_id, utc_now


CHAT_ROLES = {"user", "assistant"}
CHAT_ACTION_STATUSES = {
    "pending",
    "executing",
    "waiting_approval",
    "completed",
    "cancelled",
    "failed",
}
AGENT_RUN_STATUSES = {"running", "waiting_approval", "completed", "cancelled", "failed"}
AGENT_STEP_STATUSES = {"planned", "running", "waiting_approval", "completed", "failed", "cancelled"}


@dataclass
class ChatMessageRecord:
    role: str
    content: str
    message_id: str = field(default_factory=lambda: new_id("chat_message"))
    created_at: datetime = field(default_factory=utc_now)
    provider: str | None = None
    model: str | None = None
    total_tokens: int | None = None
    cost: float | None = None
    fallback_used: bool | None = None
    failed: bool = False
    action: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        self.role = self.role.strip().lower()
        self.content = self.content.strip()
        if self.role not in CHAT_ROLES:
            raise ValueError("chat message role must be user or assistant")
        if not self.content:
            raise ValueError("chat message content is required")
        if len(self.content) > 12000:
            raise ValueError("chat message content exceeds 12000 characters")
        if self.total_tokens is not None and self.total_tokens < 0:
            raise ValueError("chat message total_tokens cannot be negative")
        if self.cost is not None and self.cost < 0:
            raise ValueError("chat message cost cannot be negative")


@dataclass
class AgentRunStepRecord:
    sequence: int
    intent: str
    status: str = "planned"
    tool_id: str | None = None
    tool_input: dict[str, Any] = field(default_factory=dict)
    task_id: str | None = None
    approval_id: str | None = None
    observation: str | None = None
    usage: dict[str, Any] | None = None
    step_id: str = field(default_factory=lambda: new_id("agent_step"))
    created_at: datetime = field(default_factory=utc_now)
    completed_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise ValueError("agent run step sequence must be positive")
        if self.status not in AGENT_STEP_STATUSES:
            raise ValueError("invalid agent run step status")


@dataclass
class ChatAgentRunRecord:
    session_id: str
    proposal_id: str
    objective: str
    provider: str
    model: str
    max_steps: int = 8
    status: str = "running"
    steps: list[AgentRunStepRecord] = field(default_factory=list)
    final_answer: str | None = None
    error: str | None = None
    run_id: str = field(default_factory=lambda: new_id("agent_run"))
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not self.objective.strip():
            raise ValueError("agent run objective is required")
        if self.max_steps < 1 or self.max_steps > 12:
            raise ValueError("agent run max_steps must be between 1 and 12")
        if self.status not in AGENT_RUN_STATUSES:
            raise ValueError("invalid agent run status")


@dataclass
class ChatSessionRecord:
    owner_id: str = "human_root"
    title: str = "New chat"
    messages: list[ChatMessageRecord] = field(default_factory=list)
    session_id: str = field(default_factory=lambda: new_id("chat_session"))
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    import_key: str | None = None
    agent_runs: list[ChatAgentRunRecord] = field(default_factory=list)


class ChatSessionStore:
    def __init__(self, sessions: list[ChatSessionRecord] | None = None) -> None:
        self._sessions = {session.session_id: session for session in sessions or []}
        self._lock = RLock()

    def create(self, owner_id: str = "human_root", title: str = "New chat") -> ChatSessionRecord:
        clean_title = title.strip()[:80] or "New chat"
        session = ChatSessionRecord(owner_id=owner_id, title=clean_title)
        with self._lock:
            self._sessions[session.session_id] = session
        return session

    def import_session(self, session: ChatSessionRecord) -> ChatSessionRecord:
        with self._lock:
            if session.import_key:
                duplicate = next(
                    (item for item in self._sessions.values() if item.import_key == session.import_key),
                    None,
                )
                if duplicate is not None:
                    return duplicate
            existing = self._sessions.get(session.session_id)
            if existing is not None:
                return existing
            self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> ChatSessionRecord:
        with self._lock:
            return self._sessions[session_id]

    def list(self, owner_id: str | None = None) -> list[ChatSessionRecord]:
        with self._lock:
            sessions = list(self._sessions.values())
        if owner_id is not None:
            sessions = [session for session in sessions if session.owner_id == owner_id]
        return sorted(sessions, key=lambda session: session.updated_at, reverse=True)

    def delete(self, session_id: str, owner_id: str = "human_root") -> ChatSessionRecord:
        with self._lock:
            session = self._sessions[session_id]
            if session.owner_id != owner_id:
                raise PermissionError("chat session belongs to another owner")
            return self._sessions.pop(session_id)

    def append_message(self, session_id: str, message: ChatMessageRecord) -> ChatSessionRecord:
        with self._lock:
            session = self._sessions[session_id]
            session.messages.append(message)
            if message.role == "user" and len(session.messages) == 1:
                session.title = message.content.replace("\n", " ")[:28]
            session.updated_at = message.created_at
            return session

    def add_agent_run(self, session_id: str, run: ChatAgentRunRecord) -> ChatSessionRecord:
        with self._lock:
            session = self._sessions[session_id]
            existing = next((item for item in session.agent_runs if item.run_id == run.run_id), None)
            if existing is None:
                session.agent_runs.append(run)
            session.updated_at = utc_now()
            return session

    def find_agent_run(
        self,
        run_id: str,
    ) -> tuple[ChatSessionRecord, ChatAgentRunRecord] | None:
        with self._lock:
            for session in self._sessions.values():
                for run in session.agent_runs:
                    if run.run_id == run_id:
                        return session, run
        return None

    def find_agent_run_by_proposal(
        self,
        proposal_id: str,
    ) -> tuple[ChatSessionRecord, ChatAgentRunRecord] | None:
        with self._lock:
            for session in self._sessions.values():
                for run in session.agent_runs:
                    if run.proposal_id == proposal_id:
                        return session, run
        return None

    def find_agent_run_by_task(
        self,
        task_id: str,
    ) -> tuple[ChatSessionRecord, ChatAgentRunRecord, AgentRunStepRecord] | None:
        with self._lock:
            for session in self._sessions.values():
                for run in session.agent_runs:
                    for step in run.steps:
                        if step.task_id == task_id:
                            return session, run, step
        return None

    def find_by_proposal(
        self,
        proposal_id: str,
    ) -> tuple[ChatSessionRecord, ChatMessageRecord] | None:
        with self._lock:
            for session in self._sessions.values():
                for message in session.messages:
                    if message.action and message.action.get("proposal_id") == proposal_id:
                        return session, message
        return None

    def update_action(
        self,
        proposal_id: str,
        *,
        status: str,
        task_id: str | None = None,
        approval_id: str | None = None,
        risk_level: str | None = None,
        approval_input: dict[str, Any] | None = None,
    ) -> ChatSessionRecord | None:
        if status not in CHAT_ACTION_STATUSES:
            raise ValueError("invalid chat action status")
        with self._lock:
            for session in self._sessions.values():
                for message in session.messages:
                    action = message.action
                    if not action or action.get("proposal_id") != proposal_id:
                        continue
                    action["status"] = status
                    if task_id:
                        action["task_id"] = task_id
                    if approval_id:
                        action["approval_id"] = approval_id
                    if risk_level:
                        action["risk_level"] = risk_level
                    if approval_input is not None:
                        action["approval_input"] = approval_input
                    session.updated_at = utc_now()
                    return session
        return None

    def find_by_task(self, task_id: str) -> tuple[ChatSessionRecord, ChatMessageRecord] | None:
        with self._lock:
            for session in self._sessions.values():
                for message in session.messages:
                    if message.action and message.action.get("task_id") == task_id:
                        return session, message
        return None
