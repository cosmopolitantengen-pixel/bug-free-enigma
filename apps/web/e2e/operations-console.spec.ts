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
      agent_count: 17,
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

async function mockApi(page: Page, options: MockApiOptions = {}) {
  const state: { authHeaders: string[]; workflowRequest?: WorkflowRequest; actions: MutatingRequest[] } = { authHeaders: [], actions: [] };
  await page.route(`${apiBase}/**`, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const auth = request.headers().authorization;
    if (auth) state.authHeaders.push(auth);

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
    await page.getByLabel("聊天消息").fill("帮我设计一个三步发布计划");
    await page.getByRole("button", { name: "发送消息" }).click();

    await expect(page.locator(".chat-message.user").getByText("帮我设计一个三步发布计划")).toBeVisible();
    await expect(page.getByText("DeepSeek generated result")).toBeVisible();
    await expect(page.getByText("42 Token")).toBeVisible();
    expect(api.actions.find((item) => item.path === "/models/generate")?.body).toMatchObject({
      provider: "deepseek",
      model_name: "deepseek-v4-pro",
      actor_id: "ceo_agent_v1",
      purpose: "chat_conversation",
    });
    expect(String(api.actions.find((item) => item.path === "/models/generate")?.body?.prompt)).toContain("帮我设计一个三步发布计划");

    await page.getByLabel("聊天消息").fill("把第二步再说具体一点");
    await page.getByRole("button", { name: "发送消息" }).click();
    await expect(page.locator(".chat-message.user").getByText("把第二步再说具体一点")).toBeVisible();
    await expect(page.locator(".chat-message.assistant")).toHaveCount(2);
    const modelCalls = api.actions.filter((item) => item.path === "/models/generate");
    expect(modelCalls).toHaveLength(2);
    expect(String(modelCalls[1].body?.prompt)).toContain("DeepSeek generated result");
    expect(String(modelCalls[1].body?.prompt)).toContain("把第二步再说具体一点");

    await page.reload();
    await expect(page.locator(".chat-message.user").getByText("帮我设计一个三步发布计划")).toBeVisible();
    await expect(page.locator(".chat-message.user").getByText("把第二步再说具体一点")).toBeVisible();
    await expect(page.locator(".chat-message.assistant")).toHaveCount(2);
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
