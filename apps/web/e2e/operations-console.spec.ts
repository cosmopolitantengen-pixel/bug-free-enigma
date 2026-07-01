import { expect, Page, test } from "@playwright/test";

const apiBase = "http://127.0.0.1:8000";

type WorkflowRequest = {
  workflow_id?: string;
  title?: string;
  description?: string;
  input?: Record<string, unknown>;
};

type MutatingRequest = {
  method: string;
  path: string;
  body?: Record<string, unknown>;
};

type MockApiOptions = {
  failReads?: boolean;
  schedules?: Array<Record<string, unknown>>;
};

function fixtureFor(pathname: string, options: MockApiOptions = {}): unknown {
  if (options.schedules && pathname === "/schedules") return options.schedules;
  const fixtures: Record<string, unknown> = {
    "/dashboard/summary": {
      task_count: 1,
      active_scheduled_job_count: 0,
      workflow_run_count: 1,
      agent_count: 18,
      model_token_count: 0,
      integrity_issue_count: 0,
      failed_scheduled_execution_count: 0,
      recent_failed_scheduled_executions: [],
    },
    "/health": { status: "ok" },
    "/deployment/readiness": {
      status: "ready",
      checks: [{ name: "http_auth_gate", status: "ok", message: "Bearer auth configured." }],
    },
    "/system/integrity": { status: "ok", checks: [] },
    "/database/schema": { backend: "sqlite", schema_version: 1, migrations: [] },
    "/models/providers": {
      default_provider: "deepseek",
      default_model: "deepseek-v4-flash",
      providers: ["deepseek", "local"],
      fallback_order: ["local"],
      allowed_models: {
        deepseek: ["deepseek-v4-flash", "deepseek-v4-pro"],
        local: ["deterministic_mock_v1"],
      },
      provider_details: {
        deepseek: {
          default_model: "deepseek-v4-flash",
          allowed_models: ["deepseek-v4-flash", "deepseek-v4-pro"],
          pricing_usd_per_million: {
            "deepseek-v4-flash": { input: 0.14, output: 0.28 },
            "deepseek-v4-pro": { input: 0.435, output: 0.87 },
          },
        },
        local: {
          default_model: "deterministic_mock_v1",
          allowed_models: ["deterministic_mock_v1"],
          pricing_usd_per_million: {},
        },
      },
    },
    "/knowledge/embeddings/status": {
      enabled: false,
      default_model: null,
      dimensions: null,
      indexed_documents: 0,
      failed_documents: 0,
      vector_store: false,
    },
    "/alerts/status": { enabled: false, configured: false, destination: "none", endpoint_host: null, timeout_seconds: 5 },
    "/runbooks": [],
    "/tasks": [{ task_id: "task-1", title: "Initial task", status: "planned", risk_level: "low", result: null }],
    "/approvals": [{
      approval_id: "approval-1",
      status: "pending",
      request: { action: "restore_backup", actor_id: "human_root" },
    }],
    "/incidents": [{
      incident_id: "incident-1",
      title: "Queue worker failure",
      status: "open",
      risk_level: "high",
      runbook_title: "Scheduler queue recovery",
      runbook: {
        title: "Scheduler queue recovery",
        description: "Recover queue workers.",
        immediate_actions: ["Restart the failed worker pool."],
      },
    }],
    "/schedules": [{
      schedule_id: "schedule-1",
      name: "Daily readiness check",
      action: "create_task",
      status: "active",
      next_run_at: "2026-06-26T08:00:00.000Z",
    }],
    "/scheduler/executions": [],
    "/scheduler/queue-health": { status: "not_configured", queue_name: "default", worker_count: 0, queued_count: 0, started_count: 0, deferred_count: 0, failed_count: 0 },
    "/agents": [{ agent_id: "human_root", name: "Human Root", department: "root", enabled: true }],
    "/skills": [{ skill_id: "summary_skill_v1", name: "Summary", type: "native", risk_level: "low" }],
    "/tools": [{ tool_id: "task_manager_tool", name: "Task Manager", type: "internal", risk_level: "low" }],
    "/workflows": [{ workflow_id: "document_generation_v1", name: "Document Generation", execution_mode: "native" }],
    "/audit-logs": [],
    "/events": [],
  };
  return fixtures[pathname] ?? {};
}

function mockChatResponse(latest: string, body: Record<string, unknown>): Record<string, unknown> {
  const action = (
    proposal_id: string,
    workflow_id: string,
    workflow_name: string,
    input: Record<string, unknown>,
    purpose: string,
  ) => ({
    type: "action_proposal",
    message: `我可以调用“${workflow_name}”来${purpose}。确认后才会创建任务并执行。`,
    action: { proposal_id, workflow_id, workflow_name, title: latest, description: latest, input, purpose, status: "pending" },
    blocked: false,
  });
  if (body.mode === "agent") {
    const proposed = action(
      "chat-agent-1",
      "agent_run_v1",
      "Agent Run",
      { provider: body.provider, model_name: body.model_name, max_steps: 8 },
      "连续调查并完成多步工作区目标",
    );
    return { ...proposed, action: { ...(proposed.action as Record<string, unknown>), kind: "agent_run" } };
  }
  if (latest === "运行失败测试") {
    return action("chat-command-fail", "tool_call_v1", "工具调用", {
      tool_id: "workspace_command_tool", actor_id: "workspace_agent_v1", reason: latest,
      tool_input: { argv: ["python", "-c", "raise SystemExit(1)"], cwd: "." },
    }, "验证失败状态");
  }
  if (latest === "运行后端测试") {
    return action("chat-command-1", "tool_call_v1", "工具调用", {
      tool_id: "workspace_command_tool", actor_id: "workspace_agent_v1", reason: latest,
      tool_input: { argv: ["python", "-m", "unittest", "discover", "-s", "backend/tests"], cwd: "." },
    }, "运行后端测试套件");
  }
  if (latest.toLowerCase() === "git status") {
    return action("chat-tool-1", "tool_call_v1", "工具调用", {
      tool_id: "git_read_tool", actor_id: "workspace_agent_v1", reason: latest, tool_input: { operation: "status" },
    }, "读取 Git 工作区状态");
  }
  if (latest.includes("请制定")) {
    return {
      ...action("chat-action-1", "task_planning_v1", "任务规划", {}, "规划并拆分任务"),
      usage: { provider: "deepseek", model_name: "deepseek-v4-flash", total_tokens: 18 },
      cost_log: { amount: 0.000009 },
      routing: { requested_provider: "deepseek", actual_provider: "deepseek", attempted_providers: ["deepseek"], fallback_used: false },
    };
  }
  return {
    type: "conversation",
    message: "DeepSeek generated result",
    output: "DeepSeek generated result",
    usage: { provider: "deepseek", model_name: body.model_name, total_tokens: 42 },
    cost_log: { amount: 0.000021 },
    routing: { requested_provider: body.provider, actual_provider: "deepseek", attempted_providers: ["deepseek"], fallback_used: false },
    blocked: false,
  };
}

async function mockApi(page: Page, options: MockApiOptions = {}) {
  const state: { authHeaders: string[]; workflowRequest?: WorkflowRequest; actions: MutatingRequest[]; chatSessions: Array<Record<string, unknown>> } = { authHeaders: [], actions: [], chatSessions: [] };
  let chatSequence = 0;
  await page.route(`${apiBase}/**`, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const auth = request.headers().authorization;
    if (auth) state.authHeaders.push(auth);

    if (options.failReads && request.method() === "GET" && url.pathname !== "/health") {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Not authenticated" }),
      });
      return;
    }

    if (request.method() === "GET" && url.pathname === "/chat/sessions") {
      await route.fulfill({ contentType: "application/json", body: JSON.stringify(state.chatSessions) });
      return;
    }

    if (request.method() === "POST" && url.pathname === "/chat/sessions") {
      const body = request.postDataJSON() as Record<string, unknown>;
      const now = new Date().toISOString();
      const session = { session_id: `chat-session-${++chatSequence}`, title: body.title || "新对话", messages: [], created_at: now, updated_at: now };
      state.chatSessions.unshift(session);
      state.actions.push({ method: request.method(), path: url.pathname, body });
      await route.fulfill({ contentType: "application/json", body: JSON.stringify(session) });
      return;
    }

    if (request.method() === "POST" && url.pathname === "/chat/sessions/import") {
      const body = request.postDataJSON() as { sessions?: Array<Record<string, unknown>> };
      const now = new Date().toISOString();
      const imported = (body.sessions ?? []).map((item) => ({
        session_id: `chat-session-${++chatSequence}`,
        title: item.title || "导入的对话",
        messages: Array.isArray(item.messages) ? item.messages : [],
        created_at: now,
        updated_at: now,
      }));
      state.chatSessions.unshift(...imported);
      state.actions.push({ method: request.method(), path: url.pathname, body: body as unknown as Record<string, unknown> });
      await route.fulfill({ contentType: "application/json", body: JSON.stringify(imported) });
      return;
    }

    if (request.method() === "DELETE" && url.pathname.startsWith("/chat/sessions/")) {
      const sessionId = url.pathname.split("/").pop();
      state.chatSessions = state.chatSessions.filter((item) => item.session_id !== sessionId);
      state.actions.push({ method: request.method(), path: url.pathname });
      await route.fulfill({ contentType: "application/json", body: JSON.stringify({ session_id: sessionId, deleted: true }) });
      return;
    }

    if (request.method() === "POST" && /^\/chat\/sessions\/[^/]+\/messages$/.test(url.pathname)) {
      const body = request.postDataJSON() as Record<string, unknown>;
      const sessionId = url.pathname.split("/")[3];
      const session = state.chatSessions.find((item) => item.session_id === sessionId);
      const messages = (session?.messages as Array<Record<string, unknown>> | undefined) ?? [];
      const latest = String(body.content ?? "");
      const now = new Date().toISOString();
      messages.push({ message_id: `chat-message-${++chatSequence}`, role: "user", content: latest, created_at: now, failed: false, action: null });
      const response = mockChatResponse(latest, body);
      const usage = (response.usage as Record<string, unknown> | undefined) ?? {};
      const routing = (response.routing as Record<string, unknown> | undefined) ?? {};
      const cost = (response.cost_log as Record<string, unknown> | undefined) ?? {};
      const assistant = {
        message_id: `chat-message-${++chatSequence}`,
        role: "assistant",
        content: response.message,
        created_at: new Date().toISOString(),
        provider: response.usage ? routing.actual_provider || usage.provider : null,
        model: response.usage ? usage.model_name : null,
        total_tokens: response.usage ? usage.total_tokens : null,
        cost: response.usage ? cost.amount : null,
        fallback_used: response.usage ? Boolean(routing.fallback_used) : null,
        failed: Boolean(response.blocked),
        action: response.action ?? null,
      };
      messages.push(assistant);
      if (session) {
        session.messages = messages;
        if (messages.length === 2) session.title = latest.slice(0, 28);
        session.updated_at = assistant.created_at;
      }
      state.actions.push({ method: request.method(), path: url.pathname, body });
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({ session, message: assistant, response }),
      });
      return;
    }

    if (request.method() === "POST" && url.pathname === "/workflows/run") {
      state.workflowRequest = request.postDataJSON() as WorkflowRequest;
      state.actions.push({ method: request.method(), path: url.pathname, body: state.workflowRequest });
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          task: { task_id: "task-created-123456", status: "planned" },
          blocked: false,
        }),
      });
      return;
    }

    if (request.method() === "POST" && url.pathname.startsWith("/chat/actions/")) {
      state.actions.push({ method: request.method(), path: url.pathname });
      const isToolAction = url.pathname.includes("chat-tool-1");
      const isCommandAction = url.pathname.includes("chat-command-1");
      const isFailedCommandAction = url.pathname.includes("chat-command-fail");
      const isAgentAction = url.pathname.includes("chat-agent-1");
      const proposalId = url.pathname.split("/")[3];
      const chatSession = state.chatSessions.find((session) =>
        ((session.messages as Array<Record<string, unknown>> | undefined) ?? []).some((message) =>
          (message.action as Record<string, unknown> | undefined)?.proposal_id === proposalId));
      const chatMessages = (chatSession?.messages as Array<Record<string, unknown>> | undefined) ?? [];
      const proposalMessage = chatMessages.find((message) =>
        (message.action as Record<string, unknown> | undefined)?.proposal_id === proposalId);
      const proposal = proposalMessage?.action as Record<string, unknown> | undefined;
      if (isAgentAction && proposal && chatSession) {
        const now = new Date().toISOString();
        const agentRun = {
          run_id: "agent-run-1",
          proposal_id: proposalId,
          objective: proposal.description,
          status: "completed",
          error: null,
          steps: [
            { step_id: "agent-step-1", sequence: 1, intent: "list_files", status: "completed", task_id: "task-agent-1", observation: "listed workspace", created_at: now, completed_at: now },
            { step_id: "agent-step-2", sequence: 2, intent: "read_file", status: "completed", task_id: "task-agent-2", observation: "read README", created_at: now, completed_at: now },
          ],
          created_at: now,
          updated_at: now,
        };
        proposal.status = "completed";
        proposal.run_id = agentRun.run_id;
        chatSession.agent_runs = [agentRun];
        chatMessages.push({ message_id: `chat-message-${++chatSequence}`, role: "assistant", content: "Agent Run inspected the workspace safely.", created_at: now, failed: false, action: null });
        chatSession.updated_at = now;
        await route.fulfill({
          contentType: "application/json",
          body: JSON.stringify({ type: "agent_run", agent_run: agentRun, chat_session: chatSession, output: "Agent Run inspected the workspace safely.", approval_required: false, blocked: false }),
        });
        return;
      }
      if (proposal) {
        const waiting = isCommandAction || isFailedCommandAction;
        proposal.status = waiting ? "waiting_approval" : "completed";
        proposal.task_id = isFailedCommandAction ? "task-command-failed" : isCommandAction ? "task-command-123456" : isToolAction ? "task-tool-123456" : "task-created-123456";
        if (waiting) {
          proposal.approval_id = isFailedCommandAction ? "approval-command-failed" : "approval-command-1";
          proposal.risk_level = "high";
          proposal.approval_input = isFailedCommandAction
            ? { argv: ["python", "-c", "raise SystemExit(1)"], cwd: ".", timeout_seconds: 30 }
            : { argv: ["python", "-m", "unittest", "discover", "-s", "backend/tests"], cwd: ".", timeout_seconds: 120 };
        }
        const content = waiting
          ? `任务已创建，正在等待审批。任务编号：${proposal.task_id}`
          : isToolAction
            ? "行动已完成。\n## main...origin/main\n M apps/web/example.ts"
            : "行动已完成。\n# Task Plan\n\n1. Prepare\n2. Launch\n3. Review";
        chatMessages.push({ message_id: `chat-message-${++chatSequence}`, role: "assistant", content, created_at: new Date().toISOString(), failed: false, action: null });
        if (chatSession) chatSession.updated_at = new Date().toISOString();
      }
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify(isFailedCommandAction ? {
          workflow: { workflow_id: "tool_call_v1", name: "Tool Call" },
          task: { task_id: "task-command-failed", status: "needs_approval" },
          output: "Tool Call requires Human Root approval.",
          tool_run: { run_id: "tool-run-command-failed", status: "waiting_approval", risk_level: "high" },
          approval: {
            approval_id: "approval-command-failed",
            status: "pending",
            risk: { level: "high" },
            request: { metadata: { tool_input: { argv: ["python", "-c", "raise SystemExit(1)"], cwd: ".", timeout_seconds: 30 } } },
          },
          approval_required: true,
          blocked: false,
          chat_session: chatSession,
        } : isCommandAction ? {
          workflow: { workflow_id: "tool_call_v1", name: "Tool Call" },
          task: { task_id: "task-command-123456", status: "needs_approval" },
          output: "Tool Call requires Human Root approval.",
          tool_run: { run_id: "tool-run-command-1", status: "waiting_approval", risk_level: "high" },
          approval: {
            approval_id: "approval-command-1",
            status: "pending",
            risk: { level: "high" },
            request: { metadata: { tool_input: { argv: ["python", "-m", "unittest", "discover", "-s", "backend/tests"], cwd: ".", timeout_seconds: 120 } } },
          },
          approval_required: true,
          blocked: false,
          chat_session: chatSession,
        } : isToolAction ? {
          workflow: { workflow_id: "tool_call_v1", name: "Tool Call" },
          task: { task_id: "task-tool-123456", status: "completed" },
          output: "Tool Call completed",
          tool_run: { status: "completed", result: JSON.stringify({ operation: "status", output: "## main...origin/main\n M apps/web/example.ts" }) },
          approval_required: false,
          blocked: false,
          chat_session: chatSession,
        } : {
          workflow: { workflow_id: "task_planning_v1", name: "Task Planning" },
          task: { task_id: "task-created-123456", status: "planned" },
          output: "# Task Plan\n\n1. Prepare\n2. Launch\n3. Review",
          approval_required: false,
          blocked: false,
          chat_session: chatSession,
        }),
      });
      return;
    }

    if (request.method() === "POST" && url.pathname === "/tasks/task-command-failed/decision") {
      const body = request.postDataJSON() as Record<string, unknown>;
      state.actions.push({ method: request.method(), path: url.pathname, body });
      const chatSession = state.chatSessions.find((session) =>
        ((session.messages as Array<Record<string, unknown>> | undefined) ?? []).some((message) =>
          (message.action as Record<string, unknown> | undefined)?.task_id === "task-command-failed"));
      const chatMessages = (chatSession?.messages as Array<Record<string, unknown>> | undefined) ?? [];
      const proposalMessage = chatMessages.find((message) =>
        (message.action as Record<string, unknown> | undefined)?.task_id === "task-command-failed");
      if (proposalMessage?.action) (proposalMessage.action as Record<string, unknown>).status = "failed";
      chatMessages.push({ message_id: `chat-message-${++chatSequence}`, role: "assistant", content: "行动执行失败：command exited with status 1", created_at: new Date().toISOString(), failed: true, action: null });
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          task: { task_id: "task-command-failed", status: "failed" },
          output: "command exited with status 1",
          outcome: "failed",
          tool_run: { status: "failed", error: "command exited with status 1", result: null },
          approval_required: false,
          blocked: false,
          chat_session: chatSession,
        }),
      });
      return;
    }

    if (request.method() === "POST" && url.pathname === "/tasks/task-command-123456/decision") {
      const body = request.postDataJSON() as Record<string, unknown>;
      state.actions.push({ method: request.method(), path: url.pathname, body });
      const rejected = body.status === "rejected";
      const chatSession = state.chatSessions.find((session) =>
        ((session.messages as Array<Record<string, unknown>> | undefined) ?? []).some((message) =>
          (message.action as Record<string, unknown> | undefined)?.task_id === "task-command-123456"));
      const chatMessages = (chatSession?.messages as Array<Record<string, unknown>> | undefined) ?? [];
      const proposalMessage = chatMessages.find((message) =>
        (message.action as Record<string, unknown> | undefined)?.task_id === "task-command-123456");
      if (proposalMessage?.action) (proposalMessage.action as Record<string, unknown>).status = rejected ? "cancelled" : "completed";
      chatMessages.push({
        message_id: `chat-message-${++chatSequence}`,
        role: "assistant",
        content: rejected ? "Human Root 已拒绝，本次行动没有执行。" : "审批通过，行动已完成。\nRan 229 tests in 58.9s\nOK",
        created_at: new Date().toISOString(),
        failed: false,
        action: null,
      });
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify(rejected ? {
          task: { task_id: "task-command-123456", status: "cancelled" },
          output: "Human Root rejected Tool execution.",
          outcome: "rejected",
          approval_required: false,
          blocked: false,
          chat_session: chatSession,
        } : {
          task: { task_id: "task-command-123456", status: "completed" },
          output: "Tool Call completed",
          outcome: "completed",
          tool_run: { status: "completed", result: JSON.stringify({ exit_code: 0, stdout: "Ran 229 tests in 58.9s\nOK", stderr: "" }) },
          approval_required: false,
          blocked: false,
          chat_session: chatSession,
        }),
      });
      return;
    }

    if (request.method() === "POST" && url.pathname === "/models/generate") {
      const body = request.postDataJSON() as Record<string, unknown>;
      state.actions.push({ method: request.method(), path: url.pathname, body });
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          output: "DeepSeek generated result",
          usage: { provider: "deepseek", model_name: body.model_name, total_tokens: 42 },
          cost_log: { amount: 0.000021 },
          routing: {
            requested_provider: body.provider,
            actual_provider: "deepseek",
            attempted_providers: ["deepseek"],
            fallback_used: false,
          },
          blocked: false,
        }),
      });
      return;
    }

    if (request.method() === "POST" && url.pathname === "/chat/respond") {
      const body = request.postDataJSON() as Record<string, unknown>;
      const messages = body.messages as Array<{ role: string; content: string }>;
      const latest = messages[messages.length - 1]?.content ?? "";
      state.actions.push({ method: request.method(), path: url.pathname, body });
      if (latest === "运行失败测试") {
        await route.fulfill({
          contentType: "application/json",
          body: JSON.stringify({
            type: "action_proposal",
            message: "我可以调用“工具调用”来验证失败状态。确认后才会创建任务并执行。",
            action: {
              proposal_id: "chat-command-fail",
              workflow_id: "tool_call_v1",
              workflow_name: "工具调用",
              title: latest,
              description: latest,
              input: { tool_id: "workspace_command_tool", actor_id: "workspace_agent_v1", reason: latest, tool_input: { argv: ["python", "-c", "raise SystemExit(1)"], cwd: "." } },
              purpose: "验证失败状态",
              status: "pending",
            },
            blocked: false,
          }),
        });
      } else if (latest === "运行后端测试") {
        await route.fulfill({
          contentType: "application/json",
          body: JSON.stringify({
            type: "action_proposal",
            message: "我可以调用“工具调用”来运行后端测试套件。确认后才会创建任务并执行。",
            action: {
              proposal_id: "chat-command-1",
              workflow_id: "tool_call_v1",
              workflow_name: "工具调用",
              title: latest,
              description: latest,
              input: { tool_id: "workspace_command_tool", actor_id: "workspace_agent_v1", reason: latest, tool_input: { argv: ["python", "-m", "unittest", "discover", "-s", "backend/tests"], cwd: "." } },
              purpose: "运行后端测试套件",
              status: "pending",
            },
            blocked: false,
          }),
        });
      } else if (latest.toLowerCase() === "git status") {
        await route.fulfill({
          contentType: "application/json",
          body: JSON.stringify({
            type: "action_proposal",
            message: "我可以调用“工具调用”来读取 Git 工作区状态。确认后才会创建任务并执行。",
            action: {
              proposal_id: "chat-tool-1",
              workflow_id: "tool_call_v1",
              workflow_name: "工具调用",
              title: latest,
              description: latest,
              input: { tool_id: "git_read_tool", actor_id: "workspace_agent_v1", reason: latest, tool_input: { operation: "status" } },
              purpose: "读取 Git 工作区状态",
              status: "pending",
            },
            blocked: false,
          }),
        });
      } else if (latest.includes("请制定")) {
        await route.fulfill({
          contentType: "application/json",
          body: JSON.stringify({
            type: "action_proposal",
            message: "我可以调用“任务规划”来规划并拆分任务。确认后才会创建任务并执行。",
            action: {
              proposal_id: "chat-action-1",
              workflow_id: "task_planning_v1",
              workflow_name: "任务规划",
              title: latest,
              description: latest,
              input: {},
              purpose: "规划并拆分任务",
              status: "pending",
            },
            usage: { provider: "deepseek", model_name: "deepseek-v4-flash", total_tokens: 18 },
            cost_log: { amount: 0.000009 },
            routing: { requested_provider: "deepseek", actual_provider: "deepseek", attempted_providers: ["deepseek"], fallback_used: false },
            blocked: false,
          }),
        });
      } else {
        await route.fulfill({
          contentType: "application/json",
          body: JSON.stringify({
            type: "conversation",
            message: "DeepSeek generated result",
            output: "DeepSeek generated result",
            usage: { provider: "deepseek", model_name: body.model_name, total_tokens: 42 },
            cost_log: { amount: 0.000021 },
            routing: {
              requested_provider: body.provider,
              actual_provider: "deepseek",
              attempted_providers: ["deepseek"],
              fallback_used: false,
            },
            blocked: false,
          }),
        });
      }
      return;
    }

    if (request.method() === "POST") {
      const body = request.postDataJSON() as Record<string, unknown> | undefined;
      state.actions.push({ method: request.method(), path: url.pathname, body });
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({ ok: true }),
      });
      return;
    }

    if (options.failReads && request.method() === "GET" && url.pathname !== "/health") {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Not authenticated" }),
      });
      return;
    }

    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(fixtureFor(url.pathname, options)),
    });
  });
  return state;
}

test.describe("AI Company OS operations console", () => {
  test("loads production readiness and core operator views on desktop", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop-chromium", "Desktop navigation smoke runs only on the desktop project.");
    await mockApi(page);
    await page.goto("/");

    await expect(page.getByRole("heading", { name: "对话" })).toBeVisible();
    await expect(page.getByText("开始一段新对话")).toBeVisible();
    await page.getByRole("button", { name: /总览/ }).click();
    await expect(page.getByRole("heading", { name: "总览" })).toBeVisible();
    await expect(page.getByText("任务", { exact: true })).toBeVisible();
    await expect(page.getByText("Initial task")).toBeVisible();

    await page.getByRole("button", { name: /系统设置/ }).click();
    await expect(page.getByRole("heading", { name: "系统设置" })).toBeVisible();
    await expect(page.getByText("生产就绪检查")).toBeVisible();
    await expect(page.getByText("http_auth_gate")).toBeVisible();
    await expect(page.getByText("模型路由与价格")).toBeVisible();
    await expect(page.getByText(/deepseek-v4-pro：输入 \$0.435/)).toBeVisible();

    await page.getByRole("button", { name: /能力目录/ }).click();
    await expect(page.getByRole("heading", { name: "能力目录" })).toBeVisible();
    await expect(page.getByPlaceholder("搜索智能体、技能、工具和工作流")).toBeVisible();
  });

  test("sends a multi-turn chat and restores it after reload", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop-chromium", "Chat smoke runs only on the desktop project.");
    const api = await mockApi(page);
    await page.goto("/");

    await page.getByLabel("对话模型服务商").selectOption("deepseek");
    await page.getByLabel("对话模型", { exact: true }).selectOption("deepseek-v4-pro");
    await page.getByLabel("聊天消息").fill("我在考虑三种发布方向，先陪我梳理一下");
    await page.getByRole("button", { name: "发送消息" }).click();

    await expect(page.locator(".chat-message.user").getByText("我在考虑三种发布方向，先陪我梳理一下")).toBeVisible();
    await expect(page.getByText("DeepSeek generated result")).toBeVisible();
    await expect(page.getByText("42 Token")).toBeVisible();
    expect(api.actions.find((item) => item.path.endsWith("/messages"))?.body).toMatchObject({
      content: "我在考虑三种发布方向，先陪我梳理一下",
      provider: "deepseek",
      model_name: "deepseek-v4-pro",
      mode: "auto",
    });

    await page.getByLabel("聊天消息").fill("第二个方向的优势是什么");
    await page.getByRole("button", { name: "发送消息" }).click();
    await expect(page.locator(".chat-message.user").getByText("第二个方向的优势是什么")).toBeVisible();
    await expect(page.locator(".chat-message.assistant")).toHaveCount(2);
    const chatCalls = api.actions.filter((item) => item.path.endsWith("/messages"));
    expect(chatCalls).toHaveLength(2);
    expect(chatCalls[1].body).toMatchObject({ content: "第二个方向的优势是什么" });
    expect((api.chatSessions[0].messages as Array<Record<string, unknown>>).map((message) => message.content)).toEqual([
      "我在考虑三种发布方向，先陪我梳理一下",
      "DeepSeek generated result",
      "第二个方向的优势是什么",
      "DeepSeek generated result",
    ]);

    await page.reload();
    await expect(page.locator(".chat-message.user").getByText("我在考虑三种发布方向，先陪我梳理一下")).toBeVisible();
    await expect(page.locator(".chat-message.user").getByText("第二个方向的优势是什么")).toBeVisible();
    await expect(page.locator(".chat-message.assistant")).toHaveCount(2);
  });

  test("runs a governed multi-step Agent Run from chat", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop-chromium", "Agent Run smoke runs only on the desktop project.");
    const api = await mockApi(page);
    await page.goto("/");

    await page.getByLabel("对话模式").selectOption("agent");
    await page.getByLabel("聊天消息").fill("Inspect the workspace and summarize the architecture.");
    await page.getByRole("button", { name: "发送消息" }).click();

    await expect(page.getByText("agent_run_v1")).toBeVisible();
    await page.getByRole("button", { name: "确认执行" }).click();

    await expect(page.getByText("2 / 8 步")).toBeVisible();
    await expect(page.getByText("list files", { exact: true })).toBeVisible();
    await expect(page.getByText("read file", { exact: true })).toBeVisible();
    await expect(page.getByText("Agent Run inspected the workspace safely.")).toBeVisible();
    expect(api.actions.find((item) => item.path.endsWith("/messages"))?.body).toMatchObject({ mode: "agent" });
  });

  test("confirms a chat action before running its workflow", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop-chromium", "Chat action smoke runs only on the desktop project.");
    const api = await mockApi(page);
    await page.goto("/");

    await page.getByLabel("聊天消息").fill("请制定一个三步产品发布计划");
    await page.getByRole("button", { name: "发送消息" }).click();
    await expect(page.getByText("我可以调用“任务规划”来规划并拆分任务。确认后才会创建任务并执行。")).toBeVisible();
    await expect(page.getByText("task_planning_v1")).toBeVisible();
    await expect(page.getByText("18 Token")).toBeVisible();
    expect(api.actions.filter((item) => item.path.startsWith("/chat/actions/"))).toHaveLength(0);

    await page.getByRole("button", { name: "确认执行" }).click();
    await expect(page.getByText(/行动已完成/)).toBeVisible();
    expect(api.actions.filter((item) => item.path === "/chat/actions/chat-action-1/execute")).toHaveLength(1);
  });

  test("returns Git tool output inside the chat", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop-chromium", "Workspace tool smoke runs only on the desktop project.");
    const api = await mockApi(page);
    await page.goto("/");

    await page.getByLabel("聊天消息").fill("git status");
    await page.getByRole("button", { name: "发送消息" }).click();
    await expect(page.getByText("读取 Git 工作区状态", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "确认执行" }).click();

    await expect(page.getByText(/## main\.\.\.origin\/main/)).toBeVisible();
    expect(api.actions.filter((item) => item.path === "/chat/actions/chat-tool-1/execute")).toHaveLength(1);
  });

  test("approves and resumes a high-risk command inside chat after reload", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop-chromium", "Inline approval smoke runs only on the desktop project.");
    const api = await mockApi(page);
    await page.goto("/");

    await page.getByLabel("聊天消息").fill("运行后端测试");
    await page.getByRole("button", { name: "发送消息" }).click();
    await page.getByRole("button", { name: "确认执行" }).click();

    await expect(page.getByText("风险：高")).toBeVisible();
    await expect(page.getByText(/python -m unittest discover -s backend\/tests/)).toBeVisible();
    await expect(page.getByRole("button", { name: "批准并继续" })).toBeVisible();

    await page.reload();
    await expect(page.getByRole("button", { name: "批准并继续" })).toBeVisible();
    await page.getByRole("button", { name: "批准并继续" }).click();

    await expect(page.getByText(/Ran 229 tests in 58\.9s/)).toBeVisible();
    expect(api.actions.filter((item) => item.path === "/tasks/task-command-123456/decision")).toHaveLength(1);
    expect(api.actions.find((item) => item.path === "/tasks/task-command-123456/decision")?.body).toMatchObject({ status: "approved", decided_by: "human_root" });
  });

  test("shows an approved command failure as failed instead of completed", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop-chromium", "Command failure smoke runs only on the desktop project.");
    await mockApi(page);
    await page.goto("/");

    await page.getByLabel("聊天消息").fill("运行失败测试");
    await page.getByRole("button", { name: "发送消息" }).click();
    await page.getByRole("button", { name: "确认执行" }).click();
    await page.getByRole("button", { name: "批准并继续" }).click();

    await expect(page.getByText(/行动执行失败：command exited with status 1/)).toBeVisible();
    await expect(page.locator(".chat-action-card.failed")).toBeVisible();
  });

  test("persists bearer token and submits a controlled workflow", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop-chromium", "Workflow submission smoke runs only on the desktop project.");
    const api = await mockApi(page);
    await page.goto("/");

    await page.getByRole("button", { name: /系统设置/ }).click();
    await page.getByLabel("访问令牌").fill("local-token");
    await page.getByRole("button", { name: "保存令牌" }).click();
    await expect(page.getByText("API 访问令牌已保存到当前浏览器。")).toBeVisible();
    await expect.poll(() => api.authHeaders).toContain("Bearer local-token");

    await page.getByRole("button", { name: /工作台/ }).click();
    await page.getByLabel("标题").fill("Browser E2E workflow");
    await page.getByLabel("说明").fill("Exercise the operator workflow submission path.");
    await page.getByLabel("工作流输入（JSON）").fill("{\"source\":\"playwright\"}");
    await page.getByRole("button", { name: "创建并运行" }).click();

    await expect(page.getByText(/工作流已受理：/)).toBeVisible();
    expect(api.workflowRequest).toMatchObject({
      workflow_id: "document_generation_v1",
      title: "Browser E2E workflow",
      description: "Exercise the operator workflow submission path.",
      input: { source: "playwright" },
    });
  });

  test("selects a provider and model for controlled generation", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop-chromium", "Model routing smoke runs only on the desktop project.");
    const api = await mockApi(page);
    await page.goto("/");

    await page.getByRole("button", { name: /工作台/ }).click();
    await page.getByLabel("模型服务商").selectOption("deepseek");
    await page.getByRole("combobox", { name: "模型", exact: true }).selectOption("deepseek-v4-pro");
    await page.getByLabel("提示词").fill("请生成一份多模型路由测试结果。");
    await page.getByRole("button", { name: "调用模型" }).click();

    await expect(page.getByText("模型调用已完成。")).toBeVisible();
    await expect(page.getByText("DeepSeek generated result")).toBeVisible();
    await expect(page.getByText("降级发生")).toBeVisible();
    expect(api.actions.find((item) => item.path === "/models/generate")?.body).toMatchObject({
      provider: "deepseek",
      model_name: "deepseek-v4-pro",
      actor_id: "document_agent_v1",
      purpose: "console_generation",
    });
  });

  test("approves work and resolves incidents from operator views", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop-chromium", "Operator mutation smoke runs only on the desktop project.");
    const api = await mockApi(page);
    await page.goto("/");

    await page.getByRole("button", { name: /工作台/ }).click();
    await page.getByTitle("批准").click();
    await expect(page.getByText("审批已批准。")).toBeVisible();

    await page.getByRole("button", { name: /治理中心/ }).click();
    await expect(page.getByText("Restart the failed worker pool.")).toBeVisible();
    await page.getByRole("button", { name: "确认" }).click();
    await expect(page.getByText("事件已确认。")).toBeVisible();
    await page.getByRole("button", { name: "解决" }).click();
    await expect(page.getByText("事件已解决。")).toBeVisible();

    expect(api.actions.map((item) => item.path)).toEqual(expect.arrayContaining([
      "/approvals/approval-1/approve",
      "/incidents/incident-1/acknowledge",
      "/incidents/incident-1/resolve",
    ]));
  });

  test("rejects approvals and controls paused schedules", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop-chromium", "Reject/resume/cancel smoke runs only on the desktop project.");
    const api = await mockApi(page, {
      schedules: [{
        schedule_id: "schedule-paused",
        name: "Paused readiness check",
        action: "create_task",
        status: "paused",
        next_run_at: "2026-06-26T08:00:00.000Z",
      }],
    });
    await page.goto("/");

    await page.getByRole("button", { name: /工作台/ }).click();
    await page.getByTitle("拒绝").click();
    await expect(page.getByText("审批已拒绝。")).toBeVisible();

    await page.getByRole("button", { name: /计划任务/ }).click();
    await expect(page.getByText("Paused readiness check")).toBeVisible();
    await page.getByRole("button", { name: "恢复" }).click();
    await expect(page.getByText("计划任务已恢复。")).toBeVisible();
    await page.getByRole("button", { name: "取消" }).click();
    await expect(page.getByText("计划任务已取消。")).toBeVisible();

    expect(api.actions.map((item) => item.path)).toEqual(expect.arrayContaining([
      "/approvals/approval-1/reject",
      "/schedules/schedule-paused/resume",
      "/schedules/schedule-paused/cancel",
    ]));
  });

  test("creates and pauses schedules from the scheduler view", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop-chromium", "Schedule mutation smoke runs only on the desktop project.");
    const api = await mockApi(page);
    await page.goto("/");

    await page.getByRole("button", { name: /计划任务/ }).click();
    await page.getByLabel("计划名称").fill("Playwright readiness check");
    await page.getByLabel("任务标题").fill("Verify production readiness");
    await page.getByLabel("任务说明").fill("Check deployment readiness from the operator console.");
    await page.getByRole("button", { name: "创建计划任务" }).click();
    await expect(page.getByText("计划任务已创建。")).toBeVisible();

    await expect(page.getByText("Daily readiness check")).toBeVisible();
    await page.getByRole("button", { name: "暂停" }).click();
    await expect(page.getByText("计划任务已暂停。")).toBeVisible();

    expect(api.actions.map((item) => item.path)).toEqual(expect.arrayContaining([
      "/schedules",
      "/schedules/schedule-1/pause",
    ]));
    expect(api.actions.find((item) => item.path === "/schedules")?.body).toMatchObject({
      name: "Playwright readiness check",
      action: "create_task",
      payload: {
        title: "Verify production readiness",
        description: "Check deployment readiness from the operator console.",
      },
    });
  });

  test("shows safe errors for invalid input and auth-required API degradation", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop-chromium", "Failure-path smoke runs only on the desktop project.");
    await mockApi(page, { failReads: true });
    await page.goto("/");

    await expect(page.getByText("API 部分异常")).toBeVisible();
    await expect(page.getByText(/生产就绪：Not authenticated/)).toBeVisible();

    await page.getByRole("button", { name: /系统设置/ }).click();
    await page.getByLabel("API 地址").fill("localhost:8000");
    await page.getByRole("button", { name: "应用连接" }).click();
    await expect(page.getByText("API 地址必须以 http:// 或 https:// 开头")).toBeVisible();
  });

  test("uses the mobile navigation drawer at 390 px", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "mobile-chromium", "Mobile drawer smoke runs only on the mobile project.");
    await mockApi(page);
    await page.goto("/");

    await expect(page.getByRole("heading", { name: "对话", level: 1 })).toBeVisible();
    await page.getByRole("button", { name: "打开导航" }).click();
    await page.getByRole("button", { name: /计划任务/ }).click();
    await expect(page.getByRole("heading", { name: "计划任务", level: 1 })).toBeVisible();
    await expect(page.getByRole("heading", { name: "队列健康" })).toBeVisible();
  });
});
