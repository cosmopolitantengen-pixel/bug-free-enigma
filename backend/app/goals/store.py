from __future__ import annotations

from app.core.models import StrategicGoal


class GoalStore:
    def __init__(self, goals: list[StrategicGoal] | None = None) -> None:
        self._goals: dict[str, StrategicGoal] = {goal.goal_id: goal for goal in goals or []}

    def create(self, goal: StrategicGoal) -> StrategicGoal:
        self._goals[goal.goal_id] = goal
        return goal

    def get(self, goal_id: str) -> StrategicGoal:
        return self._goals[goal_id]

    def list(self, status: str | None = None, owner_agent: str | None = None) -> list[StrategicGoal]:
        goals = list(self._goals.values())
        if status is not None:
            goals = [goal for goal in goals if goal.status.value == status]
        if owner_agent is not None:
            goals = [goal for goal in goals if goal.owner_agent == owner_agent]
        return goals
