const state = {
  apiBase: "http://127.0.0.1:8000",
};

const $ = (id) => document.getElementById(id);

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function api(path, options = {}) {
  const response = await fetch(`${state.apiBase}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || `Request failed: ${response.status}`);
  }
  return payload;
}

function setText(id, value) {
  $(id).textContent = value;
}

function renderCounts(targetId, counts) {
  const entries = Object.entries(counts || {});
  $(targetId).innerHTML = entries.length
    ? entries
        .map(([key, value]) => `<li><strong>${escapeHtml(key)}</strong><span>${escapeHtml(value)}</span></li>`)
        .join("")
    : `<li><span>No data yet</span></li>`;
}

function renderList(targetId, items, formatter) {
  $(targetId).innerHTML = items?.length
    ? items.map(formatter).join("")
    : `<div class="item"><span>No records yet</span></div>`;
}

function renderDashboard(summary) {
  setText("system-health", summary.system_health || "--");
  setText("integrity-status", summary.integrity_status || "--");
  setText("integrity-issue-count", summary.integrity_issue_count || 0);
  setText("task-count", summary.task_count || 0);
  setText("strategic-goal-count", summary.strategic_goal_count || 0);
  setText("active-strategic-goal-count", summary.active_strategic_goal_count || 0);
  setText("goal-progress", summary.average_goal_progress ?? "--");
  setText("approval-count", summary.pending_approval_count || 0);
  setText("risk-count", summary.recent_risk_count || 0);
  setText("audit-count", summary.audit_log_count || 0);
  setText("structured-log-count", summary.structured_log_count || 0);
  setText("tool-count", summary.tool_count || 0);
  setText("tool-run-count", summary.tool_run_count || 0);
  setText("skill-run-count", summary.skill_run_count || 0);
  setText("workflow-run-count", summary.workflow_run_count || 0);
  setText("workflow-step-count", summary.workflow_step_count || 0);
  setText("scheduled-job-count", summary.scheduled_job_count || 0);
  setText("active-scheduled-job-count", summary.active_scheduled_job_count || 0);
  setText("domain-event-count", summary.domain_event_count || 0);
  setText("model-usage-count", summary.model_usage_count || 0);
  setText("model-token-count", summary.model_token_count || 0);
  setText("cost-log-count", summary.cost_log_count || 0);
  setText("budget-used-cost", `$${summary.budget_used_cost ?? 0}`);
  setText("incident-count", summary.incident_count || 0);
  setText("open-incident-count", summary.open_incident_count || 0);
  setText("backup-count", summary.backup_count || 0);
  setText("agent-message-count", summary.agent_message_count || 0);
  setText("agent-meeting-count", summary.agent_meeting_count || 0);
  setText("task-handoff-count", summary.task_handoff_count || 0);
  setText("agent-broadcast-count", summary.agent_broadcast_count || 0);
  setText("open-agent-conflict-count", summary.open_agent_conflict_count || 0);
  setText("task-review-count", summary.task_review_count || 0);
  setText("review-score", summary.average_review_score ?? "--");
  setText("improvement-proposal-count", summary.improvement_proposal_count || 0);
  setText("github-absorption-count", summary.github_absorption_count || 0);
  setText("evaluation-count", summary.evaluation_count || 0);
  setText("evaluation-score", summary.average_evaluation_score ?? "--");
  setText("agent-count", summary.agent_count || 0);
  setText("skill-count", summary.skill_count || 0);
  setText("memory-count", summary.memory_count || 0);
  setText("knowledge-count", summary.knowledge_count || 0);
  renderCounts("task-states", summary.task_status_counts);
  renderCounts("skill-risks", summary.skill_risk_counts);
  renderList("approvals-list", summary.recent_approvals, (approval) => `
    <div class="item approval-item">
      <strong>${escapeHtml(approval.status)}</strong>
      <span>${escapeHtml(approval.request?.action)} by ${escapeHtml(approval.request?.actor_id)}</span>
      ${
        approval.status === "pending"
          ? `<div class="actions">
              <button type="button" data-approval-action="approve" data-approval-id="${escapeHtml(approval.approval_id)}">Approve</button>
              <button type="button" class="secondary" data-approval-action="reject" data-approval-id="${escapeHtml(approval.approval_id)}">Reject</button>
            </div>`
          : ""
      }
    </div>
  `);
  renderList("risks-list", summary.recent_risks, (risk) => `
    <div class="item">
      <strong class="${risk.risk_level === "forbidden" ? "danger" : "warn"}">${escapeHtml(risk.risk_level)}</strong>
      <span>${escapeHtml(risk.action)} / ${escapeHtml(risk.result)}</span>
    </div>
  `);
  renderList("audit-list", summary.recent_logs, (event) => `
    <div class="row">
      <div>
        <strong>${escapeHtml(event.event_type)}</strong>
        <span>${escapeHtml(event.action)}</span>
      </div>
      <span>${escapeHtml(event.actor_id)}</span>
      <span>${escapeHtml(event.risk_level)}</span>
    </div>
  `);
}

function renderBudgetPolicyForm(budget) {
  $("budget-policy-name").value = budget.policy_name || "Default Model Budget";
  $("budget-max-tokens-per-call").value = budget.max_tokens_per_call ?? 2000;
  $("budget-max-total-tokens").value = budget.max_total_tokens ?? 100000;
  $("budget-max-estimated-cost").value = budget.max_estimated_cost ?? 10;
  $("budget-cost-per-token").value = budget.cost_per_token ?? 0.000001;
  $("budget-currency").value = budget.currency || "USD";
  $("budget-enabled").value = budget.enabled ? "true" : "false";
}

function renderDatabaseSchema(schema) {
  const version = schema.schema_version === null || schema.schema_version === undefined
    ? schema.backend
    : `${schema.backend} v${schema.schema_version}`;
  setText("db-schema-version", version);
  renderList("database-migrations-list", schema.migrations || [], (migration) => `
    <div class="item">
      <strong>${escapeHtml(migration.migration_id)} / v${escapeHtml(migration.version)}</strong>
      <span>${escapeHtml(migration.description)}</span>
      <span>${escapeHtml(migration.applied_at)}</span>
    </div>
  `);
}

function renderSystemIntegrity(integrity) {
  setText("integrity-status", integrity.status || "--");
  setText("integrity-issue-count", integrity.issue_count || 0);
  renderList("integrity-checks-list", integrity.checks || [], (check) => `
    <div class="row">
      <div>
        <strong>${escapeHtml(check.name)} / ${escapeHtml(check.status)}</strong>
        <span>${escapeHtml(check.message)}</span>
      </div>
      <span>${escapeHtml(check.details ? `${check.details.length} details` : "")}</span>
    </div>
  `);
}

async function refresh() {
  const [summary, databaseSchema, integrity, goals, agents, skills, skillRuns, tools, toolRuns, workflows, workflowRuns, modelUsage, budget, costLogs, incidents, backups, schedules, scheduledExecutions, domainEvents, agentMessages, agentMeetings, taskHandoffs, agentBroadcasts, agentConflicts, skillProposals, agentProposals, improvementProposals, githubAbsorptions, structuredLogs, memory, knowledge, evaluations, taskReviews] = await Promise.all([
    api("/dashboard/summary"),
    api("/database/schema"),
    api("/system/integrity"),
    api("/goals"),
    api("/agents"),
    api("/skills"),
    api("/skills/runs"),
    api("/tools"),
    api("/tools/runs"),
    api("/workflows"),
    api("/workflow-runs"),
    api("/model-usage"),
    api("/budget/summary"),
    api("/cost-logs"),
    api("/incidents"),
    api("/backups"),
    api("/schedules"),
    api("/scheduler/executions"),
    api("/events?limit=20"),
    api("/agent-messages"),
    api("/agent-meetings"),
    api("/task-handoffs"),
    api("/agent-broadcasts"),
    api("/agent-conflicts"),
    api("/skills/proposals"),
    api("/agents/proposals"),
    api("/improvement-proposals"),
    api("/github/absorptions"),
    api("/logs/structured?limit=20"),
    api("/memory"),
    api("/knowledge"),
    api("/evaluations"),
    api("/task-reviews"),
  ]);

  renderDashboard(summary);
  renderDatabaseSchema(databaseSchema);
  renderSystemIntegrity(integrity);
  renderBudgetPolicyForm(budget);
  renderList("goals-list", goals.slice(-6), (goal) => `
    <div class="item">
      <strong>${escapeHtml(goal.title)} / ${escapeHtml(goal.status)}</strong>
      <span>${escapeHtml(goal.owner_agent)} / ${escapeHtml(goal.current_value)} of ${escapeHtml(goal.target_value)} ${escapeHtml(goal.target_metric)}</span>
      <span>tasks: ${escapeHtml((goal.linked_task_ids || []).length)} / reviews: ${escapeHtml((goal.linked_review_ids || []).length)} / improvements: ${escapeHtml((goal.linked_improvement_ids || []).length)}</span>
    </div>
  `);
  renderList("agents-list", agents.slice(0, 8), (agent) => `
    <div class="item">
      <strong>${escapeHtml(agent.name)}</strong>
      <span>${escapeHtml(agent.department)} / ${escapeHtml(agent.risk_level)}</span>
    </div>
  `);
  renderList("skills-list", skills.slice(0, 8), (skill) => `
    <div class="item">
      <strong>${escapeHtml(skill.name)}</strong>
      <span>${escapeHtml(skill.type)} / ${escapeHtml(skill.risk_level)}</span>
    </div>
  `);
  renderList("skill-runs-list", skillRuns.slice(-8), (run) => `
    <div class="item">
      <strong>${escapeHtml(run.skill_id)} / ${escapeHtml(run.status)}</strong>
      <span>${escapeHtml(run.actor_id)} / ${escapeHtml(run.risk_level)}</span>
      <span>${escapeHtml(run.error || run.result || "No result yet").slice(0, 180)}</span>
      ${run.status === "waiting_approval" ? `<div class="actions"><button type="button" data-skill-run-action="complete" data-skill-run-id="${escapeHtml(run.run_id)}">Complete</button></div>` : ""}
    </div>
  `);
  renderList("tools-list", tools.slice(0, 8), (tool) => `
    <div class="item">
      <strong>${escapeHtml(tool.name)}</strong>
      <span>${escapeHtml(tool.type)} / ${escapeHtml(tool.risk_level)} / ${tool.enabled ? "enabled" : "disabled"}</span>
    </div>
  `);
  renderList("tool-runs-list", toolRuns.slice(-8), (run) => `
    <div class="item">
      <strong>${escapeHtml(run.tool_id)} / ${escapeHtml(run.status)}</strong>
      <span>${escapeHtml(run.actor_id)} / ${escapeHtml(run.action)} / ${escapeHtml(run.risk_level)}</span>
      <span>${escapeHtml(run.error || run.result || "No result yet").slice(0, 180)}</span>
      ${
        run.status === "waiting_approval"
          ? `<div class="actions">
              <button type="button" data-tool-run-action="complete" data-tool-run-id="${escapeHtml(run.run_id)}">Complete</button>
            </div>`
          : ""
      }
    </div>
  `);
  renderList("workflow-catalog-list", workflows, (workflow) => `
    <div class="item">
      <strong>${escapeHtml(workflow.name)} / ${escapeHtml(workflow.execution_mode)}</strong>
      <span>${escapeHtml(workflow.workflow_id)} / ${escapeHtml(workflow.steps.length)} steps</span>
      <span>${escapeHtml(workflow.entrypoint)}</span>
    </div>
  `);
  renderList("workflow-runs-list", workflowRuns.slice(-8), (run) => `
    <div class="item">
      <strong>${escapeHtml(run.workflow_id)} / ${escapeHtml(run.status)}</strong>
      <span>${escapeHtml(run.task_id)} / ${escapeHtml(run.result || "running")}</span>
      ${
        run.status === "waiting_approval"
          ? `<div class="actions">
              <button type="button" data-workflow-action="resume" data-task-id="${escapeHtml(run.task_id)}">Resume</button>
            </div>`
          : ""
      }
    </div>
  `);
  renderList("workflow-steps-list", (summary.recent_workflow_steps || []).slice(-8), (step) => `
    <div class="item">
      <strong>${escapeHtml(step.sequence)}. ${escapeHtml(step.step_name)} / ${escapeHtml(step.status)}</strong>
      <span>${escapeHtml(step.actor_id)} / ${escapeHtml(step.action)} / ${escapeHtml(step.result)}</span>
    </div>
  `);
  renderList("model-usage-list", modelUsage.slice(-8), (usage) => `
    <div class="item">
      <strong>${escapeHtml(usage.model_name)} / ${escapeHtml(usage.total_tokens)} tokens</strong>
      <span>${escapeHtml(usage.actor_id)} / ${escapeHtml(usage.purpose)} / $${escapeHtml(usage.estimated_cost)}</span>
    </div>
  `);
  renderList("budget-summary", [budget], (item) => `
    <div class="item">
      <strong>${escapeHtml(item.policy_name)} / ${item.enabled ? "enabled" : "disabled"}</strong>
      <span>${escapeHtml(item.used_tokens)} of ${escapeHtml(item.max_total_tokens)} tokens / $${escapeHtml(item.used_cost)} of $${escapeHtml(item.max_estimated_cost)}</span>
    </div>
  `);
  renderList("cost-logs-list", costLogs.slice(-6), (log) => `
    <div class="item">
      <strong>${escapeHtml(log.result)} / ${escapeHtml(log.tokens)} tokens / $${escapeHtml(log.amount)}</strong>
      <span>${escapeHtml(log.actor_id)} / ${escapeHtml(log.source_type)} / ${escapeHtml(log.reason)}</span>
    </div>
  `);
  renderList("incidents-list", incidents.slice(-8), (incident) => `
    <div class="item">
      <strong>${escapeHtml(incident.title)} / ${escapeHtml(incident.status)}</strong>
      <span>${escapeHtml(incident.risk_level)} / ${escapeHtml(incident.source_type)} / ${escapeHtml(incident.description)}</span>
      ${
        incident.status !== "resolved"
          ? `<div class="actions">
              <button type="button" data-incident-action="acknowledge" data-incident-id="${escapeHtml(incident.incident_id)}">Ack</button>
              <button type="button" class="secondary" data-incident-action="resolve" data-incident-id="${escapeHtml(incident.incident_id)}">Resolve</button>
            </div>`
          : ""
      }
    </div>
  `);
  renderList("backups-list", backups.slice(-6), (backup) => {
    const approvedRestore = [...(summary.recent_approvals || [])].reverse().find(
      (approval) =>
        approval.status === "approved" &&
        approval.request?.action === "restore_backup" &&
        approval.request?.target === backup.backup_id,
    );
    return `
      <div class="item">
        <strong>${escapeHtml(backup.backup_id)}</strong>
        <span>${escapeHtml(backup.actor_id)} / ${escapeHtml(backup.reason)}</span>
        <span>checksum: ${escapeHtml(backup.backup_checksum || "missing").slice(0, 24)}</span>
        <span>${escapeHtml(backup.rollback_plan)}</span>
        <div class="actions">
          <button type="button" data-backup-action="verify" data-backup-id="${escapeHtml(backup.backup_id)}">Verify</button>
          <button type="button" class="secondary" data-backup-action="restore" data-backup-id="${escapeHtml(backup.backup_id)}">Request Restore</button>
          ${
            approvedRestore
              ? `<button type="button" data-backup-action="execute" data-backup-id="${escapeHtml(backup.backup_id)}" data-approval-id="${escapeHtml(approvedRestore.approval_id)}">Apply Approved Restore</button>`
              : ""
          }
        </div>
      </div>
    `;
  });
  renderList("schedules-list", schedules.slice(-8), (job) => `
    <div class="item">
      <strong>${escapeHtml(job.name)} / ${escapeHtml(job.status)}</strong>
      <span>${escapeHtml(job.action)} / next: ${escapeHtml(job.next_run_at)}</span>
      <span>runs: ${escapeHtml(job.run_count)} / failures: ${escapeHtml(job.failure_count)}${job.interval_seconds ? ` / every ${escapeHtml(job.interval_seconds)}s` : " / one-time"}</span>
      ${job.last_error ? `<span class="danger">${escapeHtml(job.last_error)}</span>` : ""}
      ${
        ["active", "paused"].includes(job.status)
          ? `<div class="actions">
              ${job.status === "active" ? `<button type="button" data-schedule-action="pause" data-schedule-id="${escapeHtml(job.schedule_id)}">Pause</button>` : `<button type="button" data-schedule-action="resume" data-schedule-id="${escapeHtml(job.schedule_id)}">Resume</button>`}
              <button type="button" class="secondary" data-schedule-action="cancel" data-schedule-id="${escapeHtml(job.schedule_id)}">Cancel</button>
            </div>`
          : ""
      }
    </div>
  `);
  renderList("scheduled-executions-list", scheduledExecutions.slice(-8), (execution) => `
    <div class="item">
      <strong>${escapeHtml(execution.action)} / ${escapeHtml(execution.status)}</strong>
      <span>${escapeHtml(execution.schedule_id)} / ${escapeHtml(execution.completed_at)}</span>
      <span>${escapeHtml(execution.output_ref || execution.error || "no output")}</span>
    </div>
  `);
  renderList("domain-events-list", domainEvents.slice(-12), (event) => `
    <div class="row">
      <div>
        <strong>${escapeHtml(event.event_type)}</strong>
        <span>${escapeHtml(event.source_type)} / ${escapeHtml(event.source_id)}</span>
      </div>
      <span>${escapeHtml(event.actor_id)}</span>
      <span>${escapeHtml(event.created_at)}</span>
    </div>
  `);
  renderList("agent-messages-list", agentMessages.slice(-6), (message) => `
    <div class="item">
      <strong>${escapeHtml(message.message_type)} / ${escapeHtml(message.priority)}</strong>
      <span>${escapeHtml(message.from_agent)} -> ${escapeHtml(message.to_agent)}${message.requires_response ? " / response required" : ""}</span>
      <span>${escapeHtml(message.content).slice(0, 180)}</span>
    </div>
  `);
  renderList("agent-meetings-list", agentMeetings.slice(-4), (meeting) => `
    <div class="item">
      <strong>${escapeHtml(meeting.title)} / ${escapeHtml(meeting.meeting_type)}</strong>
      <span>${escapeHtml(meeting.organizer_agent)} with ${escapeHtml((meeting.participant_agents || []).join(", "))}</span>
      <span>${escapeHtml(meeting.minutes || meeting.agenda).slice(0, 180)}</span>
    </div>
  `);
  renderList("task-handoffs-list", taskHandoffs.slice(-6), (handoff) => `
    <div class="item">
      <strong>${escapeHtml(handoff.task_id)} / ${escapeHtml(handoff.task_status)}</strong>
      <span>${escapeHtml(handoff.from_agent)} -> ${escapeHtml(handoff.to_agent)}</span>
      <span>${escapeHtml(handoff.instructions || handoff.reason).slice(0, 180)}</span>
    </div>
  `);
  renderList("agent-broadcasts-list", agentBroadcasts.slice(-6), (broadcast) => `
    <div class="item">
      <strong>${escapeHtml(broadcast.event_type)} / ${escapeHtml(broadcast.priority)}</strong>
      <span>${escapeHtml(broadcast.from_agent)} -> ${escapeHtml((broadcast.audience_agents || []).join(", "))}</span>
      <span>${escapeHtml(broadcast.title)}: ${escapeHtml(broadcast.content).slice(0, 160)}</span>
    </div>
  `);
  renderList("agent-conflicts-list", agentConflicts.slice(-6), (conflict) => `
    <div class="item">
      <strong>${escapeHtml(conflict.issue).slice(0, 120)} / ${escapeHtml(conflict.status)}</strong>
      <span>${escapeHtml(conflict.raised_by_agent)} vs ${escapeHtml((conflict.opposing_agents || []).join(", "))} / ${escapeHtml(conflict.priority_area)}</span>
      <span>${escapeHtml(conflict.resolution || "Awaiting arbitration").slice(0, 180)}</span>
    </div>
  `);
  const proposals = [
    ...skillProposals.map((proposal) => ({ ...proposal, proposal_type: "skill" })),
    ...agentProposals.map((proposal) => ({ ...proposal, proposal_type: "agent" })),
    ...improvementProposals.map((proposal) => ({ ...proposal, proposal_type: "improvement", name: proposal.title })),
  ];
  renderList("proposals-list", proposals.slice(-8), (proposal) => `
    <div class="item">
      <strong>${escapeHtml(proposal.name)}</strong>
      <span>${escapeHtml(proposal.proposal_type)} / ${escapeHtml(proposal.status)} / sandbox: ${escapeHtml(proposal.sandbox_status || "not_run")} / ${escapeHtml(proposal.risk_level)}</span>
      ${proposal.sandbox_notes ? `<span>${escapeHtml(proposal.sandbox_notes)}</span>` : ""}
      ${
        proposal.sandbox_status !== "passed"
          ? `<div class="actions">
              <button type="button" data-proposal-action="sandbox" data-proposal-type="${escapeHtml(proposal.proposal_type)}" data-proposal-id="${escapeHtml(proposal.proposal_id)}">Sandbox</button>
            </div>`
          : ""
      }
      ${
        proposal.status === "approved" && proposal.sandbox_status === "passed"
          ? `<div class="actions">
              <button type="button" data-proposal-action="register" data-proposal-type="${escapeHtml(proposal.proposal_type)}" data-proposal-id="${escapeHtml(proposal.proposal_id)}">Register</button>
            </div>`
          : ""
      }
    </div>
  `);
  renderList("github-absorptions-list", githubAbsorptions.slice(-8), (proposal) => `
    <div class="item">
      <strong>${escapeHtml(proposal.repo_url)}</strong>
      <span>${escapeHtml(proposal.status)} / sandbox: ${escapeHtml(proposal.sandbox_status || "not_run")} / ${escapeHtml(proposal.risk_level)} / ${escapeHtml(proposal.license_name)}</span>
      <span>${escapeHtml(proposal.summary).slice(0, 180)}</span>
      ${proposal.sandbox_notes ? `<span>${escapeHtml(proposal.sandbox_notes)}</span>` : ""}
      ${
        proposal.sandbox_status !== "passed"
          ? `<div class="actions">
              <button type="button" data-github-action="sandbox" data-github-id="${escapeHtml(proposal.proposal_id)}">Sandbox</button>
            </div>`
          : ""
      }
      ${
        proposal.status === "approved" && proposal.sandbox_status === "passed"
          ? `<div class="actions">
              <button type="button" data-github-action="register" data-github-id="${escapeHtml(proposal.proposal_id)}">Register Knowledge</button>
            </div>`
          : ""
      }
    </div>
  `);
  renderList("structured-logs-list", structuredLogs.slice(-12), (log) => `
    <div class="row">
      <div>
        <strong>${escapeHtml(log.event_type)} / ${escapeHtml(log.level)}</strong>
        <span>${escapeHtml(log.message)}</span>
      </div>
      <span>${escapeHtml(log.category)}</span>
      <span>${escapeHtml(log.actor_id || log.source_id)}</span>
    </div>
  `);
  renderList("memory-list", memory.slice(-6), (record) => `
    <div class="item">
      <strong>${escapeHtml(record.memory_type)}</strong>
      <span>${escapeHtml(record.content).slice(0, 180)}</span>
    </div>
  `);
  renderList("knowledge-list", knowledge.slice(-6), (doc) => `
    <div class="item">
      <strong>${escapeHtml(doc.title)}</strong>
      <span>${escapeHtml(doc.content).slice(0, 180)}</span>
    </div>
  `);
  renderList("evaluations-list", evaluations.slice(-6), (record) => `
    <div class="item">
      <strong>${escapeHtml(record.subject_type)} / ${escapeHtml(record.score)}</strong>
      <span>${escapeHtml(record.subject_id)} / ${escapeHtml(record.metric)}</span>
    </div>
  `);
  renderList("task-reviews-list", taskReviews.slice(-6), (review) => `
    <div class="item">
      <strong>${escapeHtml(review.outcome)} / ${escapeHtml(review.quality_score)}</strong>
      <span>${escapeHtml(review.task_id)} / ${escapeHtml(review.reviewer_agent)}</span>
      <span>${escapeHtml(review.summary).slice(0, 180)}</span>
    </div>
  `);
}

async function createAndRunTask(event) {
  event.preventDefault();
  $("task-result").textContent = "Creating task...";

  try {
    const result = await api("/workflows/run", {
      method: "POST",
      body: JSON.stringify({
        workflow_id: $("task-workflow").value,
        title: $("task-title").value,
        description: $("task-description").value,
        input: JSON.parse($("task-workflow-input").value || "{}"),
      }),
    });
    $("task-result").innerHTML = `<span class="ok">Workflow result:</span> ${escapeHtml(result.task.status)} (${escapeHtml(result.task.task_id)})`;
    $("goal-link-record-id").value = result.task.task_id;
    await refresh();
  } catch (error) {
    $("task-result").innerHTML = `<span class="danger">${escapeHtml(error.message)}</span>`;
  }
}

async function requestApproval(event) {
  event.preventDefault();
  $("approval-request-result").textContent = "Submitting approval request...";

  try {
    const result = await api("/approvals/request", {
      method: "POST",
      body: JSON.stringify({
        action: $("approval-action").value,
        actor_id: $("approval-actor").value,
        permission_level: $("approval-permission").value,
        reason: $("approval-reason").value,
        possible_benefit: "Human Root can review the action before execution.",
        possible_loss: "The action may be unsafe or unauthorized without approval.",
      }),
    });
    const status = result.approval?.status || result.result;
    const klass = status === "blocked" ? "danger" : status === "pending" ? "warn" : "ok";
    $("approval-request-result").innerHTML = `<span class="${klass}">${escapeHtml(status)}</span> / ${escapeHtml(result.risk.level)}`;
    await refresh();
  } catch (error) {
    $("approval-request-result").innerHTML = `<span class="danger">${escapeHtml(error.message)}</span>`;
  }
}

async function requestToolRun(event) {
  event.preventDefault();
  $("tool-run-result").textContent = "Requesting tool run...";

  try {
    const result = await api("/tools/runs/request", {
      method: "POST",
      body: JSON.stringify({
        tool_id: $("tool-run-tool").value,
        actor_id: $("tool-run-actor").value,
        reason: $("tool-run-reason").value,
        input: { source: "dashboard" },
      }),
    });
    const status = result.run.status;
    const klass = status === "blocked" ? "danger" : status === "waiting_approval" ? "warn" : "ok";
    $("tool-run-result").innerHTML = `<span class="${klass}">${escapeHtml(status)}</span> / ${escapeHtml(result.tool.name)}`;
    await refresh();
  } catch (error) {
    $("tool-run-result").innerHTML = `<span class="danger">${escapeHtml(error.message)}</span>`;
  }
}

async function requestSkillRun(event) {
  event.preventDefault();
  $("skill-run-result").textContent = "Requesting Skill run...";
  try {
    const result = await api("/skills/runs/request", {
      method: "POST",
      body: JSON.stringify({
        skill_id: $("skill-run-skill").value,
        actor_id: $("skill-run-actor").value,
        reason: $("skill-run-reason").value,
        input: JSON.parse($("skill-run-input").value),
      }),
    });
    const status = result.run.status;
    const klass = status === "blocked" || status === "failed" ? "danger" : status === "waiting_approval" ? "warn" : "ok";
    $("skill-run-result").innerHTML = `<span class="${klass}">${escapeHtml(status)}</span> / ${escapeHtml(result.skill.name)}`;
    await refresh();
  } catch (error) {
    $("skill-run-result").innerHTML = `<span class="danger">${escapeHtml(error.message)}</span>`;
  }
}

async function generateModelResponse(event) {
  event.preventDefault();
  $("model-result").textContent = "Generating...";

  try {
    const result = await api("/models/generate", {
      method: "POST",
      body: JSON.stringify({
        actor_id: $("model-actor").value,
        purpose: $("model-purpose").value,
        prompt: $("model-prompt").value,
      }),
    });
    $("model-result").innerHTML = `<span class="ok">Generated:</span> ${escapeHtml(result.output).slice(0, 220)}`;
    await refresh();
  } catch (error) {
    $("model-result").innerHTML = `<span class="danger">${escapeHtml(error.message)}</span>`;
  }
}

async function decideApproval(approvalId, decision) {
  const endpoint = decision === "approve" ? "approve" : "reject";
  const status = decision === "approve" ? "approved" : "rejected";
  await api(`/approvals/${approvalId}/${endpoint}`, {
    method: "POST",
    body: JSON.stringify({
      status,
      decided_by: "human_root",
      note: `${status} from dashboard`,
    }),
  });
  await refresh();
}

async function registerProposal(proposalId, proposalType) {
  const path = proposalType === "agent"
    ? `/agents/proposals/${proposalId}/register`
    : proposalType === "improvement"
      ? `/improvement-proposals/${proposalId}/register`
      : `/skills/proposals/${proposalId}/register`;
  await api(path, { method: "POST" });
  await refresh();
}

async function sandboxProposal(proposalId, proposalType) {
  const path = proposalType === "agent"
    ? `/agents/proposals/${proposalId}/sandbox`
    : proposalType === "improvement"
      ? `/improvement-proposals/${proposalId}/sandbox`
      : `/skills/proposals/${proposalId}/sandbox`;
  await api(path, { method: "POST" });
  await refresh();
}

async function analyzeGitHubAbsorption(event) {
  event.preventDefault();
  $("github-absorption-result").textContent = "Analyzing repository metadata...";

  try {
    const result = await api("/github/absorptions/analyze", {
      method: "POST",
      body: JSON.stringify({
        repo_url: $("github-repo-url").value,
        requested_by_agent: $("github-requested-by").value,
        license_name: $("github-license").value,
        maintenance_signal: $("github-maintenance").value,
        readme: $("github-readme").value,
      }),
    });
    $("github-absorption-result").innerHTML = `<span class="ok">Analyzed:</span> ${escapeHtml(result.proposal_id)} / ${escapeHtml(result.risk_level)}`;
    await refresh();
  } catch (error) {
    $("github-absorption-result").innerHTML = `<span class="danger">${escapeHtml(error.message)}</span>`;
  }
}

async function updateGitHubAbsorption(proposalId, action) {
  const path = action === "register"
    ? `/github/absorptions/${proposalId}/register`
    : `/github/absorptions/${proposalId}/sandbox`;
  await api(path, { method: "POST" });
  await refresh();
}

async function updateIncident(incidentId, action) {
  const path = action === "resolve"
    ? `/incidents/${incidentId}/resolve`
    : `/incidents/${incidentId}/acknowledge`;
  await api(path, {
    method: "POST",
    body: JSON.stringify({
      actor_id: "human_root",
      note: `${action} from dashboard`,
    }),
  });
  await refresh();
}

async function completeToolRun(runId) {
  await api(`/tools/runs/${runId}/complete`, {
    method: "POST",
    body: JSON.stringify({
      completed_by: "human_root",
      note: "completed from dashboard after approval",
    }),
  });
  await refresh();
}

async function completeSkillRun(runId) {
  const result = await api(`/skills/runs/${runId}/complete`, {
    method: "POST",
    body: JSON.stringify({ completed_by: "human_root", note: "Completed from dashboard after approval." }),
  });
  $("skill-run-result").innerHTML = `<span class="ok">${escapeHtml(result.run.status)}</span> / ${escapeHtml(result.skill.name)}`;
  await refresh();
}

async function resumeTask(taskId) {
  const result = await api(`/tasks/${taskId}/resume`, { method: "POST" });
  $("task-result").innerHTML = `<span class="ok">Resumed:</span> ${escapeHtml(result.task.status)} (${escapeHtml(result.task.task_id)})`;
  await refresh();
}

async function updateBudgetPolicy(event) {
  event.preventDefault();
  $("budget-policy-result").textContent = "Updating budget policy...";

  try {
    const result = await api("/budget/policy", {
      method: "POST",
      body: JSON.stringify({
        actor_id: "human_root",
        name: $("budget-policy-name").value,
        max_tokens_per_call: Number($("budget-max-tokens-per-call").value),
        max_total_tokens: Number($("budget-max-total-tokens").value),
        max_estimated_cost: Number($("budget-max-estimated-cost").value),
        cost_per_token: Number($("budget-cost-per-token").value),
        currency: $("budget-currency").value,
        enabled: $("budget-enabled").value === "true",
      }),
    });
    $("budget-policy-result").innerHTML = `<span class="ok">Updated:</span> ${escapeHtml(result.policy_name)} / ${escapeHtml(result.max_total_tokens)} tokens`;
    await refresh();
  } catch (error) {
    $("budget-policy-result").innerHTML = `<span class="danger">${escapeHtml(error.message)}</span>`;
  }
}

async function createBackup(event) {
  event.preventDefault();
  $("backup-result").textContent = "Creating backup...";

  try {
    const result = await api("/backups", {
      method: "POST",
      body: JSON.stringify({
        actor_id: "human_root",
        reason: $("backup-reason").value,
      }),
    });
    $("backup-result").innerHTML = `<span class="ok">Created:</span> ${escapeHtml(result.backup_id)} / ${escapeHtml(result.backup_checksum).slice(0, 24)}`;
    await refresh();
  } catch (error) {
    $("backup-result").innerHTML = `<span class="danger">${escapeHtml(error.message)}</span>`;
  }
}

async function verifyBackup(backupId) {
  const result = await api(`/backups/${backupId}/verify`, {
    method: "POST",
    body: JSON.stringify({ actor_id: "human_root" }),
  });
  const klass = result.verified ? "ok" : "warn";
  $("backup-result").innerHTML = `<span class="${klass}">${escapeHtml(result.status)}</span> / ${escapeHtml(result.actual_checksum).slice(0, 24)}`;
  await refresh();
}

async function requestBackupRestore(backupId) {
  const result = await api(`/backups/${backupId}/restore-request`, {
    method: "POST",
    body: JSON.stringify({
      actor_id: "human_root",
      reason: "Dashboard restore request after checksum verification.",
    }),
  });
  const klass = result.result === "blocked" ? "danger" : "warn";
  const approvalId = result.approval?.approval_id || "no approval";
  $("backup-result").innerHTML = `<span class="${klass}">${escapeHtml(result.result)}</span> / ${escapeHtml(approvalId)}`;
  await refresh();
}

async function executeBackupRestore(backupId, approvalId) {
  const confirmed = window.confirm(
    `Apply approved backup ${backupId}? A pre-restore safety checkpoint will be created first.`,
  );
  if (!confirmed) {
    return;
  }
  const result = await api(`/backups/${backupId}/restore`, {
    method: "POST",
    body: JSON.stringify({
      approval_id: approvalId,
      actor_id: "human_root",
      reason: "Apply approved restore from dashboard.",
    }),
  });
  const klass = result.result === "restored" ? "ok" : "danger";
  const safetyBackupId = result.safety_backup?.backup_id || "no safety backup";
  $("backup-result").innerHTML = `<span class="${klass}">${escapeHtml(result.result)}</span> / safety checkpoint: ${escapeHtml(safetyBackupId)}`;
  await refresh();
}

async function createScheduledJob(event) {
  event.preventDefault();
  $("scheduler-result").textContent = "Creating schedule...";
  try {
    const action = $("schedule-action").value;
    const nextRun = new Date($("schedule-next-run").value);
    if (Number.isNaN(nextRun.getTime())) {
      throw new Error("Choose a valid next run time.");
    }
    const payload = action === "run_task"
      ? { task_id: $("schedule-task-id").value.trim() }
      : {
          title: $("schedule-task-title").value,
          description: $("schedule-task-description").value,
        };
    const intervalValue = $("schedule-interval").value;
    const maxRunsValue = $("schedule-max-runs").value;
    const result = await api("/schedules", {
      method: "POST",
      body: JSON.stringify({
        name: $("schedule-name").value,
        action,
        payload,
        created_by: "human_root",
        next_run_at: nextRun.toISOString(),
        interval_seconds: intervalValue ? Number(intervalValue) : null,
        max_runs: maxRunsValue ? Number(maxRunsValue) : null,
      }),
    });
    $("scheduler-result").innerHTML = `<span class="ok">Created:</span> ${escapeHtml(result.schedule_id)} / ${escapeHtml(result.status)}`;
    await refresh();
  } catch (error) {
    $("scheduler-result").innerHTML = `<span class="danger">${escapeHtml(error.message)}</span>`;
  }
}

async function tickScheduler() {
  $("scheduler-result").textContent = "Running due schedules...";
  const result = await api("/scheduler/tick", {
    method: "POST",
    body: JSON.stringify({ actor_id: "human_root", limit: 50 }),
  });
  $("scheduler-result").innerHTML = `<span class="ok">Tick complete:</span> ${escapeHtml(result.executed_count)} executed`;
  await refresh();
}

async function updateScheduledJob(scheduleId, action) {
  const result = await api(`/schedules/${scheduleId}/${action}`, {
    method: "POST",
    body: JSON.stringify({ actor_id: "human_root" }),
  });
  $("scheduler-result").innerHTML = `<span class="ok">${escapeHtml(action)}:</span> ${escapeHtml(result.schedule_id)} / ${escapeHtml(result.status)}`;
  await refresh();
}

async function sendAgentMessage(event) {
  event.preventDefault();
  $("agent-communication-result").textContent = "Sending message...";

  try {
    const result = await api("/agent-messages", {
      method: "POST",
      body: JSON.stringify({
        from_agent: $("agent-message-from").value,
        to_agent: $("agent-message-to").value,
        message_type: $("agent-message-type").value,
        priority: $("agent-message-priority").value,
        requires_response: $("agent-message-response").value === "true",
        content: $("agent-message-content").value,
      }),
    });
    $("agent-communication-result").innerHTML = `<span class="ok">Sent:</span> ${escapeHtml(result.message_id)}`;
    await refresh();
  } catch (error) {
    $("agent-communication-result").innerHTML = `<span class="danger">${escapeHtml(error.message)}</span>`;
  }
}

async function broadcastAgentEvent(event) {
  event.preventDefault();
  $("agent-communication-result").textContent = "Broadcasting event...";

  try {
    const result = await api("/agent-broadcasts", {
      method: "POST",
      body: JSON.stringify({
        from_agent: $("agent-broadcast-from").value,
        audience_agents: $("agent-broadcast-audience").value.split(",").map((item) => item.trim()).filter(Boolean),
        event_type: $("agent-broadcast-type").value,
        title: $("agent-broadcast-title").value,
        content: $("agent-broadcast-content").value,
      }),
    });
    $("agent-communication-result").innerHTML = `<span class="ok">Broadcast:</span> ${escapeHtml(result.broadcast_id)}`;
    await refresh();
  } catch (error) {
    $("agent-communication-result").innerHTML = `<span class="danger">${escapeHtml(error.message)}</span>`;
  }
}

async function openAgentConflict(event) {
  event.preventDefault();
  $("agent-communication-result").textContent = "Opening conflict...";

  const raisedBy = $("agent-conflict-raised-by").value;
  const opponents = $("agent-conflict-opposing").value.split(",").map((item) => item.trim()).filter(Boolean);
  const positions = {
    [raisedBy]: $("agent-conflict-raised-position").value,
  };
  opponents.forEach((agentId) => {
    positions[agentId] = $("agent-conflict-opposing-position").value;
  });

  try {
    const result = await api("/agent-conflicts", {
      method: "POST",
      body: JSON.stringify({
        raised_by_agent: raisedBy,
        opposing_agents: opponents,
        issue: $("agent-conflict-issue").value,
        priority_area: $("agent-conflict-priority").value,
        positions,
      }),
    });
    $("agent-communication-result").innerHTML = `<span class="ok">Conflict:</span> ${escapeHtml(result.conflict_id)}`;
    $("agent-conflict-resolve-id").value = result.conflict_id;
    await refresh();
  } catch (error) {
    $("agent-communication-result").innerHTML = `<span class="danger">${escapeHtml(error.message)}</span>`;
  }
}

async function resolveAgentConflict(event) {
  event.preventDefault();
  $("agent-communication-result").textContent = "Resolving conflict...";

  try {
    const result = await api(`/agent-conflicts/${$("agent-conflict-resolve-id").value}/resolve`, {
      method: "POST",
      body: JSON.stringify({
        resolved_by: $("agent-conflict-resolved-by").value,
        selected_position_agent: $("agent-conflict-selected-agent").value || null,
        resolution: $("agent-conflict-resolution").value,
      }),
    });
    $("agent-communication-result").innerHTML = `<span class="ok">Resolved:</span> ${escapeHtml(result.conflict_id)}`;
    await refresh();
  } catch (error) {
    $("agent-communication-result").innerHTML = `<span class="danger">${escapeHtml(error.message)}</span>`;
  }
}

async function handoffTask(event) {
  event.preventDefault();
  $("agent-communication-result").textContent = "Recording task handoff...";

  try {
    const result = await api(`/tasks/${$("task-handoff-task").value}/handoff`, {
      method: "POST",
      body: JSON.stringify({
        from_agent: $("task-handoff-from").value,
        to_agent: $("task-handoff-to").value,
        reason: $("task-handoff-reason").value,
        instructions: $("task-handoff-instructions").value,
      }),
    });
    $("agent-communication-result").innerHTML = `<span class="ok">Handoff:</span> ${escapeHtml(result.handoff.handoff_id)}`;
    await refresh();
  } catch (error) {
    $("agent-communication-result").innerHTML = `<span class="danger">${escapeHtml(error.message)}</span>`;
  }
}

async function recordAgentMeeting(event) {
  event.preventDefault();
  $("agent-communication-result").textContent = "Recording meeting...";

  try {
    const result = await api("/agent-meetings", {
      method: "POST",
      body: JSON.stringify({
        title: $("agent-meeting-title").value,
        organizer_agent: $("agent-meeting-organizer").value,
        participant_agents: $("agent-meeting-participants").value.split(",").map((item) => item.trim()).filter(Boolean),
        agenda: $("agent-meeting-agenda").value,
        minutes: $("agent-meeting-minutes").value,
      }),
    });
    $("agent-communication-result").innerHTML = `<span class="ok">Recorded:</span> ${escapeHtml(result.meeting_id)}`;
    await refresh();
  } catch (error) {
    $("agent-communication-result").innerHTML = `<span class="danger">${escapeHtml(error.message)}</span>`;
  }
}

function splitLines(value) {
  return value
    .split(/\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
}

async function recordTaskReview(event) {
  event.preventDefault();
  $("task-review-result").textContent = "Recording review...";

  try {
    const result = await api("/task-reviews", {
      method: "POST",
      body: JSON.stringify({
        task_id: $("task-review-task").value,
        reviewer_agent: $("task-review-reviewer").value,
        outcome: $("task-review-outcome").value,
        summary: $("task-review-summary").value,
        what_went_well: $("task-review-well").value,
        what_went_wrong: $("task-review-wrong").value,
        lessons: splitLines($("task-review-lessons").value),
        follow_up_actions: splitLines($("task-review-followups").value),
        quality_score: Number($("task-review-score").value),
      }),
    });
    $("task-review-result").innerHTML = `<span class="ok">Review:</span> ${escapeHtml(result.review.review_id)}`;
    $("improvement-review-id").value = result.review.review_id;
    $("goal-link-type").value = "review";
    $("goal-link-record-id").value = result.review.review_id;
    await refresh();
  } catch (error) {
    $("task-review-result").innerHTML = `<span class="danger">${escapeHtml(error.message)}</span>`;
  }
}

async function proposeImprovement(event) {
  event.preventDefault();
  $("improvement-proposal-result").textContent = "Creating improvement proposal...";

  try {
    const result = await api(`/task-reviews/${$("improvement-review-id").value}/improvements`, {
      method: "POST",
      body: JSON.stringify({
        proposed_by_agent: $("improvement-proposed-by").value,
        target_type: $("improvement-target-type").value,
        title: $("improvement-title").value,
        description: $("improvement-description").value,
        rationale: $("improvement-rationale").value,
        risk_level: $("improvement-risk-level").value,
      }),
    });
    $("improvement-proposal-result").innerHTML = `<span class="ok">Proposal:</span> ${escapeHtml(result.proposal_id)} / ${escapeHtml(result.status)}`;
    $("goal-link-type").value = "improvement";
    $("goal-link-record-id").value = result.proposal_id;
    await refresh();
  } catch (error) {
    $("improvement-proposal-result").innerHTML = `<span class="danger">${escapeHtml(error.message)}</span>`;
  }
}

async function createGoal(event) {
  event.preventDefault();
  $("goal-result").textContent = "Creating goal...";

  try {
    const goal = await api("/goals", {
      method: "POST",
      body: JSON.stringify({
        title: $("goal-title").value,
        description: $("goal-description").value,
        owner_agent: $("goal-owner").value,
        target_metric: $("goal-target-metric").value,
        target_value: Number($("goal-target-value").value),
      }),
    });
    $("goal-result").innerHTML = `<span class="ok">Goal:</span> ${escapeHtml(goal.goal_id)}`;
    $("goal-progress-id").value = goal.goal_id;
    $("goal-link-id").value = goal.goal_id;
    await refresh();
  } catch (error) {
    $("goal-result").innerHTML = `<span class="danger">${escapeHtml(error.message)}</span>`;
  }
}

async function updateGoalProgress(event) {
  event.preventDefault();
  $("goal-result").textContent = "Updating goal progress...";

  try {
    const goal = await api(`/goals/${$("goal-progress-id").value}/progress`, {
      method: "POST",
      body: JSON.stringify({
        current_value: Number($("goal-current-value").value),
        status: $("goal-status").value || null,
        note: $("goal-progress-note").value,
      }),
    });
    $("goal-result").innerHTML = `<span class="ok">Progress:</span> ${escapeHtml(goal.current_value)} / ${escapeHtml(goal.status)}`;
    await refresh();
  } catch (error) {
    $("goal-result").innerHTML = `<span class="danger">${escapeHtml(error.message)}</span>`;
  }
}

async function linkGoalRecord(event) {
  event.preventDefault();
  $("goal-result").textContent = "Linking record...";

  const goalId = $("goal-link-id").value;
  const recordId = $("goal-link-record-id").value;
  const linkType = $("goal-link-type").value;
  const path = linkType === "review"
    ? `/goals/${goalId}/reviews/${recordId}`
    : linkType === "improvement"
      ? `/goals/${goalId}/improvements/${recordId}`
      : `/goals/${goalId}/tasks/${recordId}`;

  try {
    const goal = await api(path, {
      method: "POST",
      body: JSON.stringify({ actor_id: "ceo_agent_v1" }),
    });
    $("goal-result").innerHTML = `<span class="ok">Linked:</span> ${escapeHtml(recordId)} -> ${escapeHtml(goal.goal_id)}`;
    await refresh();
  } catch (error) {
    $("goal-result").innerHTML = `<span class="danger">${escapeHtml(error.message)}</span>`;
  }
}

function wireNavigation() {
  document.querySelectorAll("nav a").forEach((link) => {
    link.addEventListener("click", () => {
      document.querySelectorAll("nav a").forEach((item) => item.classList.remove("active"));
      link.classList.add("active");
    });
  });
}

$("api-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  state.apiBase = $("api-base").value.replace(/\/$/, "");
  await refresh().catch((error) => {
    $("task-result").innerHTML = `<span class="danger">${escapeHtml(error.message)}</span>`;
  });
});

$("goal-form").addEventListener("submit", createGoal);
$("goal-progress-form").addEventListener("submit", updateGoalProgress);
$("goal-link-form").addEventListener("submit", linkGoalRecord);
$("task-form").addEventListener("submit", createAndRunTask);
$("approval-request-form").addEventListener("submit", requestApproval);
$("tool-run-form").addEventListener("submit", requestToolRun);
$("skill-run-form").addEventListener("submit", requestSkillRun);
$("model-form").addEventListener("submit", generateModelResponse);
$("budget-policy-form").addEventListener("submit", updateBudgetPolicy);
$("backup-form").addEventListener("submit", createBackup);
$("schedule-form").addEventListener("submit", createScheduledJob);
$("scheduler-tick").addEventListener("click", async () => {
  try {
    await tickScheduler();
  } catch (error) {
    $("scheduler-result").innerHTML = `<span class="danger">${escapeHtml(error.message)}</span>`;
  }
});
$("agent-broadcast-form").addEventListener("submit", broadcastAgentEvent);
$("agent-conflict-form").addEventListener("submit", openAgentConflict);
$("agent-conflict-resolve-form").addEventListener("submit", resolveAgentConflict);
$("task-handoff-form").addEventListener("submit", handoffTask);
$("agent-message-form").addEventListener("submit", sendAgentMessage);
$("agent-meeting-form").addEventListener("submit", recordAgentMeeting);
$("task-review-form").addEventListener("submit", recordTaskReview);
$("improvement-proposal-form").addEventListener("submit", proposeImprovement);
$("github-absorption-form").addEventListener("submit", analyzeGitHubAbsorption);
$("approvals-list").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-approval-action]");
  if (!button) {
    return;
  }
  button.disabled = true;
  try {
    await decideApproval(button.dataset.approvalId, button.dataset.approvalAction);
  } catch (error) {
    $("approval-request-result").innerHTML = `<span class="danger">${escapeHtml(error.message)}</span>`;
  } finally {
    button.disabled = false;
  }
});
$("proposals-list").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-proposal-action]");
  if (!button) {
    return;
  }
  button.disabled = true;
  try {
    if (button.dataset.proposalAction === "sandbox") {
      await sandboxProposal(button.dataset.proposalId, button.dataset.proposalType);
    } else {
      await registerProposal(button.dataset.proposalId, button.dataset.proposalType);
    }
  } catch (error) {
    $("approval-request-result").innerHTML = `<span class="danger">${escapeHtml(error.message)}</span>`;
  } finally {
    button.disabled = false;
  }
});
$("github-absorptions-list").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-github-action]");
  if (!button) {
    return;
  }
  button.disabled = true;
  try {
    await updateGitHubAbsorption(button.dataset.githubId, button.dataset.githubAction);
  } catch (error) {
    $("github-absorption-result").innerHTML = `<span class="danger">${escapeHtml(error.message)}</span>`;
  } finally {
    button.disabled = false;
  }
});
$("incidents-list").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-incident-action]");
  if (!button) {
    return;
  }
  button.disabled = true;
  try {
    await updateIncident(button.dataset.incidentId, button.dataset.incidentAction);
  } catch (error) {
    $("approval-request-result").innerHTML = `<span class="danger">${escapeHtml(error.message)}</span>`;
  } finally {
    button.disabled = false;
  }
});
$("backups-list").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-backup-action]");
  if (!button) {
    return;
  }
  button.disabled = true;
  try {
    if (button.dataset.backupAction === "execute") {
      await executeBackupRestore(button.dataset.backupId, button.dataset.approvalId);
    } else if (button.dataset.backupAction === "restore") {
      await requestBackupRestore(button.dataset.backupId);
    } else {
      await verifyBackup(button.dataset.backupId);
    }
  } catch (error) {
    $("backup-result").innerHTML = `<span class="danger">${escapeHtml(error.message)}</span>`;
  } finally {
    button.disabled = false;
  }
});
$("schedules-list").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-schedule-action]");
  if (!button) {
    return;
  }
  button.disabled = true;
  try {
    await updateScheduledJob(button.dataset.scheduleId, button.dataset.scheduleAction);
  } catch (error) {
    $("scheduler-result").innerHTML = `<span class="danger">${escapeHtml(error.message)}</span>`;
  } finally {
    button.disabled = false;
  }
});
$("tool-runs-list").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-tool-run-action]");
  if (!button) {
    return;
  }
  button.disabled = true;
  try {
    await completeToolRun(button.dataset.toolRunId);
  } catch (error) {
    $("tool-run-result").innerHTML = `<span class="danger">${escapeHtml(error.message)}</span>`;
  } finally {
    button.disabled = false;
  }
});
$("skill-runs-list").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-skill-run-action]");
  if (!button) {
    return;
  }
  button.disabled = true;
  try {
    await completeSkillRun(button.dataset.skillRunId);
  } catch (error) {
    $("skill-run-result").innerHTML = `<span class="danger">${escapeHtml(error.message)}</span>`;
  } finally {
    button.disabled = false;
  }
});
$("workflow-runs-list").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-workflow-action]");
  if (!button) {
    return;
  }
  button.disabled = true;
  try {
    await resumeTask(button.dataset.taskId);
  } catch (error) {
    $("task-result").innerHTML = `<span class="danger">${escapeHtml(error.message)}</span>`;
  } finally {
    button.disabled = false;
  }
});
const defaultScheduleTime = new Date(Date.now() + 5 * 60 * 1000);
defaultScheduleTime.setSeconds(0, 0);
const timezoneOffset = defaultScheduleTime.getTimezoneOffset() * 60 * 1000;
$("schedule-next-run").value = new Date(defaultScheduleTime.getTime() - timezoneOffset)
  .toISOString()
  .slice(0, 16);
wireNavigation();
refresh().catch((error) => {
  $("task-result").innerHTML = `<span class="danger">${escapeHtml(error.message)}</span>`;
});
