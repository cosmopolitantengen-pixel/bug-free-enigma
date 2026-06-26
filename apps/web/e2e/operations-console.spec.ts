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

function fixtureFor(pathname: string): unknown {
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
    "/models/providers": { default_provider: "local", default_model: "deterministic" },
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

async function mockApi(page: Page) {
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

    if (request.method() === "POST") {
      const body = request.postDataJSON() as Record<string, unknown> | undefined;
      state.actions.push({ method: request.method(), path: url.pathname, body });
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({ ok: true }),
      });
      return;
    }

    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(fixtureFor(url.pathname)),
    });
  });
  return state;
}

test.describe("AI Company OS operations console", () => {
  test("loads production readiness and core operator views on desktop", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop-chromium", "Desktop navigation smoke runs only on the desktop project.");
    await mockApi(page);
    await page.goto("/");

    await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
    await expect(page.getByText("Tasks")).toBeVisible();
    await expect(page.getByText("Initial task")).toBeVisible();

    await page.getByRole("button", { name: /System/ }).click();
    await expect(page.getByRole("heading", { name: "System" })).toBeVisible();
    await expect(page.getByText("Production readiness")).toBeVisible();
    await expect(page.getByText("http_auth_gate")).toBeVisible();

    await page.getByRole("button", { name: /Catalog/ }).click();
    await expect(page.getByRole("heading", { name: "Catalog" })).toBeVisible();
    await expect(page.getByPlaceholder("Search agents, skills, tools, and workflows")).toBeVisible();
  });

  test("persists bearer token and submits a controlled workflow", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop-chromium", "Workflow submission smoke runs only on the desktop project.");
    const api = await mockApi(page);
    await page.goto("/");

    await page.getByRole("button", { name: /System/ }).click();
    await page.getByLabel("Bearer token").fill("local-token");
    await page.getByRole("button", { name: "Save token" }).click();
    await expect(page.getByText("API bearer token saved for this browser.")).toBeVisible();
    await expect.poll(() => api.authHeaders).toContain("Bearer local-token");

    await page.getByRole("button", { name: /Work queue/ }).click();
    await page.getByLabel("Title").fill("Browser E2E workflow");
    await page.getByLabel("Description").fill("Exercise the operator workflow submission path.");
    await page.getByLabel("Workflow input (JSON)").fill("{\"source\":\"playwright\"}");
    await page.getByRole("button", { name: "Create and run" }).click();

    await expect(page.getByText(/Workflow accepted:/)).toBeVisible();
    expect(api.workflowRequest).toMatchObject({
      workflow_id: "document_generation_v1",
      title: "Browser E2E workflow",
      description: "Exercise the operator workflow submission path.",
      input: { source: "playwright" },
    });
  });

  test("approves work and resolves incidents from operator views", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop-chromium", "Operator mutation smoke runs only on the desktop project.");
    const api = await mockApi(page);
    await page.goto("/");

    await page.getByRole("button", { name: /Work queue/ }).click();
    await page.getByTitle("Approve").click();
    await expect(page.getByText("Approval approved.")).toBeVisible();

    await page.getByRole("button", { name: /Governance/ }).click();
    await expect(page.getByText("Restart the failed worker pool.")).toBeVisible();
    await page.getByRole("button", { name: "Acknowledge" }).click();
    await expect(page.getByText("Incident acknowledged.")).toBeVisible();
    await page.getByRole("button", { name: "Resolve" }).click();
    await expect(page.getByText("Incident resolved.")).toBeVisible();

    expect(api.actions.map((item) => item.path)).toEqual(expect.arrayContaining([
      "/approvals/approval-1/approve",
      "/incidents/incident-1/acknowledge",
      "/incidents/incident-1/resolve",
    ]));
  });

  test("creates and pauses schedules from the scheduler view", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop-chromium", "Schedule mutation smoke runs only on the desktop project.");
    const api = await mockApi(page);
    await page.goto("/");

    await page.getByRole("button", { name: /Scheduler/ }).click();
    await page.getByLabel("Schedule name").fill("Playwright readiness check");
    await page.getByLabel("Task title").fill("Verify production readiness");
    await page.getByLabel("Task description").fill("Check deployment readiness from the operator console.");
    await page.getByRole("button", { name: "Create schedule" }).click();
    await expect(page.getByText("Schedule created.")).toBeVisible();

    await expect(page.getByText("Daily readiness check")).toBeVisible();
    await page.getByRole("button", { name: "Pause" }).click();
    await expect(page.getByText("Schedule paused.")).toBeVisible();

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

  test("uses the mobile navigation drawer at 390 px", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "mobile-chromium", "Mobile drawer smoke runs only on the mobile project.");
    await mockApi(page);
    await page.goto("/");

    await page.getByRole("button", { name: "Open navigation" }).click();
    await page.getByRole("button", { name: /Scheduler/ }).click();
    await expect(page.getByRole("heading", { name: "Scheduler" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Queue health" })).toBeVisible();
  });
});
