from __future__ import annotations

from app.core.models import AgentBroadcast, AgentConflict, AgentMeeting, AgentMessage, TaskHandoff


class CommunicationStore:
    def __init__(
        self,
        messages: list[AgentMessage] | None = None,
        meetings: list[AgentMeeting] | None = None,
        handoffs: list[TaskHandoff] | None = None,
        broadcasts: list[AgentBroadcast] | None = None,
        conflicts: list[AgentConflict] | None = None,
    ) -> None:
        self._messages: dict[str, AgentMessage] = {message.message_id: message for message in messages or []}
        self._meetings: dict[str, AgentMeeting] = {meeting.meeting_id: meeting for meeting in meetings or []}
        self._handoffs: dict[str, TaskHandoff] = {handoff.handoff_id: handoff for handoff in handoffs or []}
        self._broadcasts: dict[str, AgentBroadcast] = {
            broadcast.broadcast_id: broadcast for broadcast in broadcasts or []
        }
        self._conflicts: dict[str, AgentConflict] = {conflict.conflict_id: conflict for conflict in conflicts or []}

    def send_message(self, message: AgentMessage) -> AgentMessage:
        self._messages[message.message_id] = message
        return message

    def list_messages(self, agent_id: str | None = None, task_id: str | None = None) -> list[AgentMessage]:
        messages = list(self._messages.values())
        if agent_id is not None:
            messages = [
                message
                for message in messages
                if message.from_agent == agent_id or message.to_agent == agent_id
            ]
        if task_id is not None:
            messages = [message for message in messages if message.task_id == task_id]
        return messages

    def record_meeting(self, meeting: AgentMeeting) -> AgentMeeting:
        self._meetings[meeting.meeting_id] = meeting
        return meeting

    def list_meetings(self, task_id: str | None = None) -> list[AgentMeeting]:
        meetings = list(self._meetings.values())
        if task_id is not None:
            meetings = [meeting for meeting in meetings if meeting.task_id == task_id]
        return meetings

    def record_handoff(self, handoff: TaskHandoff) -> TaskHandoff:
        self._handoffs[handoff.handoff_id] = handoff
        return handoff

    def list_handoffs(self, task_id: str | None = None, agent_id: str | None = None) -> list[TaskHandoff]:
        handoffs = list(self._handoffs.values())
        if task_id is not None:
            handoffs = [handoff for handoff in handoffs if handoff.task_id == task_id]
        if agent_id is not None:
            handoffs = [
                handoff
                for handoff in handoffs
                if handoff.from_agent == agent_id or handoff.to_agent == agent_id
            ]
        return handoffs

    def broadcast_event(self, broadcast: AgentBroadcast) -> AgentBroadcast:
        self._broadcasts[broadcast.broadcast_id] = broadcast
        return broadcast

    def list_broadcasts(
        self,
        task_id: str | None = None,
        agent_id: str | None = None,
        event_type: str | None = None,
    ) -> list[AgentBroadcast]:
        broadcasts = list(self._broadcasts.values())
        if task_id is not None:
            broadcasts = [broadcast for broadcast in broadcasts if broadcast.task_id == task_id]
        if agent_id is not None:
            broadcasts = [
                broadcast
                for broadcast in broadcasts
                if broadcast.from_agent == agent_id or agent_id in broadcast.audience_agents
            ]
        if event_type is not None:
            broadcasts = [broadcast for broadcast in broadcasts if broadcast.event_type == event_type]
        return broadcasts

    def open_conflict(self, conflict: AgentConflict) -> AgentConflict:
        self._conflicts[conflict.conflict_id] = conflict
        return conflict

    def get_conflict(self, conflict_id: str) -> AgentConflict:
        return self._conflicts[conflict_id]

    def list_conflicts(
        self,
        task_id: str | None = None,
        agent_id: str | None = None,
        status: str | None = None,
    ) -> list[AgentConflict]:
        conflicts = list(self._conflicts.values())
        if task_id is not None:
            conflicts = [conflict for conflict in conflicts if conflict.task_id == task_id]
        if agent_id is not None:
            conflicts = [
                conflict
                for conflict in conflicts
                if conflict.raised_by_agent == agent_id or agent_id in conflict.opposing_agents
            ]
        if status is not None:
            conflicts = [conflict for conflict in conflicts if conflict.status == status]
        return conflicts

    def resolve_conflict(
        self,
        conflict_id: str,
        resolved_by: str,
        resolution: str,
        selected_position_agent: str | None,
        resolved_at,
    ) -> AgentConflict:
        conflict = self._conflicts[conflict_id]
        conflict.status = "resolved"
        conflict.resolved_by = resolved_by
        conflict.resolution = resolution
        conflict.selected_position_agent = selected_position_agent
        conflict.resolved_at = resolved_at
        return conflict
