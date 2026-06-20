import os
import unittest


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


class DashboardStaticTests(unittest.TestCase):
    def test_static_dashboard_contains_required_mount_points(self):
        index_path = os.path.join(ROOT_DIR, "apps", "web_dashboard", "index.html")
        script_path = os.path.join(ROOT_DIR, "apps", "web_dashboard", "app.js")
        style_path = os.path.join(ROOT_DIR, "apps", "web_dashboard", "styles.css")

        with open(index_path, "r", encoding="utf-8") as handle:
            index = handle.read()
        with open(script_path, "r", encoding="utf-8") as handle:
            script = handle.read()
        with open(style_path, "r", encoding="utf-8") as handle:
            styles = handle.read()

        required_ids = [
            "system-health",
            "integrity-status",
            "integrity-issue-count",
            "task-count",
            "strategic-goal-count",
            "active-strategic-goal-count",
            "goal-progress",
            "approval-count",
            "risk-count",
            "audit-count",
            "structured-log-count",
            "db-schema-version",
            "workflow-run-count",
            "workflow-step-count",
            "active-scheduled-job-count",
            "domain-event-count",
            "workflow-runs-list",
            "workflow-catalog-list",
            "workflow-steps-list",
            "model-token-count",
            "model-usage-count",
            "budget-used-cost",
            "open-incident-count",
            "incident-count",
            "backup-count",
            "agent-message-count",
            "agent-meeting-count",
            "task-handoff-count",
            "agent-broadcast-count",
            "open-agent-conflict-count",
            "task-review-count",
            "improvement-proposal-count",
            "github-absorption-count",
            "cost-log-count",
            "model-form",
            "model-result",
            "model-usage-list",
            "budget-summary",
            "budget-policy-form",
            "budget-policy-name",
            "budget-max-tokens-per-call",
            "budget-max-total-tokens",
            "budget-max-estimated-cost",
            "budget-cost-per-token",
            "budget-currency",
            "budget-enabled",
            "budget-policy-result",
            "cost-logs-list",
            "incidents-list",
            "backup-form",
            "backup-reason",
            "backup-result",
            "backups-list",
            "scheduled-job-count",
            "schedule-form",
            "schedule-name",
            "schedule-action",
            "schedule-next-run",
            "schedule-interval",
            "schedule-max-runs",
            "schedule-task-id",
            "schedule-task-title",
            "schedule-task-description",
            "scheduler-tick",
            "scheduler-result",
            "schedules-list",
            "scheduled-executions-list",
            "domain-events-list",
            "agent-message-form",
            "agent-broadcast-form",
            "agent-broadcast-from",
            "agent-broadcast-audience",
            "agent-broadcast-type",
            "agent-broadcast-title",
            "agent-broadcast-content",
            "agent-conflict-form",
            "agent-conflict-raised-by",
            "agent-conflict-opposing",
            "agent-conflict-priority",
            "agent-conflict-issue",
            "agent-conflict-raised-position",
            "agent-conflict-opposing-position",
            "agent-conflict-resolve-form",
            "agent-conflict-resolve-id",
            "agent-conflict-resolved-by",
            "agent-conflict-selected-agent",
            "agent-conflict-resolution",
            "task-handoff-form",
            "task-handoff-task",
            "task-handoff-from",
            "task-handoff-to",
            "task-handoff-reason",
            "task-handoff-instructions",
            "agent-message-from",
            "agent-message-to",
            "agent-message-type",
            "agent-message-priority",
            "agent-message-response",
            "agent-message-content",
            "agent-meeting-form",
            "agent-meeting-title",
            "agent-meeting-organizer",
            "agent-meeting-participants",
            "agent-meeting-agenda",
            "agent-meeting-minutes",
            "agent-communication-result",
            "agent-conflicts-list",
            "agent-broadcasts-list",
            "task-handoffs-list",
            "agent-messages-list",
            "agent-meetings-list",
            "task-review-form",
            "task-review-task",
            "task-review-reviewer",
            "task-review-outcome",
            "task-review-score",
            "task-review-summary",
            "task-review-well",
            "task-review-wrong",
            "task-review-lessons",
            "task-review-followups",
            "task-review-result",
            "task-reviews-list",
            "review-score",
            "goal-form",
            "goal-title",
            "goal-owner",
            "goal-target-metric",
            "goal-target-value",
            "goal-description",
            "goal-progress-form",
            "goal-progress-id",
            "goal-current-value",
            "goal-status",
            "goal-progress-note",
            "goal-link-form",
            "goal-link-id",
            "goal-link-type",
            "goal-link-record-id",
            "goal-result",
            "goals-list",
            "improvement-proposal-form",
            "improvement-review-id",
            "improvement-proposed-by",
            "improvement-target-type",
            "improvement-risk-level",
            "improvement-title",
            "improvement-description",
            "improvement-rationale",
            "improvement-proposal-result",
            "github-absorption-form",
            "github-repo-url",
            "github-requested-by",
            "github-license",
            "github-maintenance",
            "github-readme",
            "github-absorption-result",
            "github-absorptions-list",
            "task-form",
            "task-workflow",
            "approval-request-form",
            "approval-request-result",
            "agents-list",
            "skills-list",
            "tool-count",
            "tool-run-count",
            "tool-run-form",
            "tool-run-result",
            "tools-list",
            "tool-runs-list",
            "approvals-list",
            "proposals-list",
            "risks-list",
            "audit-list",
            "structured-logs-list",
            "database-migrations-list",
            "integrity-checks-list",
            "memory-list",
            "knowledge-list",
            "evaluation-count",
            "evaluation-score",
            "evaluations-list",
        ]
        for element_id in required_ids:
            self.assertIn(f'id="{element_id}"', index)

        self.assertIn("/dashboard/summary", script)
        self.assertIn("/database/schema", script)
        self.assertIn("/system/integrity", script)
        self.assertIn("/goals", script)
        self.assertIn("/tasks", script)
        self.assertIn("/resume", script)
        self.assertIn("/approvals/request", script)
        self.assertIn("/skills/proposals", script)
        self.assertIn("/agents/proposals", script)
        self.assertIn("/improvement-proposals", script)
        self.assertIn("/github/absorptions", script)
        self.assertIn("/logs/structured", script)
        self.assertIn("/sandbox", script)
        self.assertIn("/tools", script)
        self.assertIn("/tools/runs", script)
        self.assertIn("/tools/runs/request", script)
        self.assertIn("/complete", script)
        self.assertIn("/workflow-runs", script)
        self.assertIn("/workflows", script)
        self.assertIn("workflow_id", script)
        self.assertIn('value="agent_collaboration_v1"', index)
        self.assertIn('value="skill_missing_v1"', index)
        self.assertIn('value="agent_missing_v1"', index)
        self.assertIn("recent_workflow_steps", script)
        self.assertIn("/model-usage", script)
        self.assertIn("/models/generate", script)
        self.assertIn("/budget/summary", script)
        self.assertIn("/budget/policy", script)
        self.assertIn("/cost-logs", script)
        self.assertIn("/incidents", script)
        self.assertIn("/backups", script)
        self.assertIn("/schedules", script)
        self.assertIn("/scheduler/executions", script)
        self.assertIn("/scheduler/tick", script)
        self.assertIn("/events?limit=20", script)
        self.assertIn("/verify", script)
        self.assertIn("/restore-request", script)
        self.assertIn("Apply Approved Restore", script)
        self.assertIn("verifyBackup", script)
        self.assertIn("requestBackupRestore", script)
        self.assertIn("executeBackupRestore", script)
        self.assertIn("createScheduledJob", script)
        self.assertIn("tickScheduler", script)
        self.assertIn("updateScheduledJob", script)
        self.assertIn("data-schedule-action", script)
        self.assertIn("data-backup-action", script)
        self.assertIn("/agent-messages", script)
        self.assertIn("/agent-meetings", script)
        self.assertIn("/task-handoffs", script)
        self.assertIn("/agent-broadcasts", script)
        self.assertIn("/agent-conflicts", script)
        self.assertIn("/task-reviews", script)
        self.assertIn("/improvements", script)
        self.assertIn("/handoff", script)
        self.assertIn("updateIncident", script)
        self.assertIn("createBackup", script)
        self.assertIn("sendAgentMessage", script)
        self.assertIn("broadcastAgentEvent", script)
        self.assertIn("openAgentConflict", script)
        self.assertIn("resolveAgentConflict", script)
        self.assertIn("handoffTask", script)
        self.assertIn("recordAgentMeeting", script)
        self.assertIn("recordTaskReview", script)
        self.assertIn("proposeImprovement", script)
        self.assertIn("analyzeGitHubAbsorption", script)
        self.assertIn("updateGitHubAbsorption", script)
        self.assertIn("createGoal", script)
        self.assertIn("updateGoalProgress", script)
        self.assertIn("linkGoalRecord", script)
        self.assertIn("resumeTask", script)
        self.assertIn("data-workflow-action", script)
        self.assertIn("generateModelResponse", script)
        self.assertIn("updateBudgetPolicy", script)
        self.assertIn("/evaluations", script)
        self.assertIn("data-proposal-action", script)
        self.assertIn("sandboxProposal", script)
        self.assertIn("data-approval-action", script)
        self.assertIn("decideApproval", script)
        self.assertIn("completeToolRun", script)
        self.assertIn("data-tool-run-action", script)
        self.assertIn('endpoint = decision === "approve" ? "approve" : "reject"', script)
        self.assertIn("@media", styles)


if __name__ == "__main__":
    unittest.main()
