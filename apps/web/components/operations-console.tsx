"use client";

import {
  Activity,
  AlertTriangle,
  Bot,
  Boxes,
  CalendarClock,
  Check,
  ChevronRight,
  CircleGauge,
  ClipboardCheck,
  Database,
  FileClock,
  ListChecks,
  Menu,
  Play,
  RefreshCw,
  Search,
  ServerCog,
  ShieldCheck,
  SlidersHorizontal,
  Workflow,
  X,
} from "lucide-react";
import { FormEvent, ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import { ApiRecord, apiRequest, formatDate, getStoredApiToken, shortId, storeApiToken, text } from "@/lib/api";

type View = "overview" | "work" | "scheduler" | "catalog" | "governance" | "system";
type DataSet = {
  summary: ApiRecord;
  health: ApiRecord;
  integrity: ApiRecord;
  schema: ApiRecord;
  providers: ApiRecord;
  embeddings: ApiRecord;
  alertStatus: ApiRecord;
  runbooks: ApiRecord[];
  tasks: ApiRecord[];
  approvals: ApiRecord[];
  incidents: ApiRecord[];
  schedules: ApiRecord[];
  executions: ApiRecord[];
  queueHealth: ApiRecord;
  agents: ApiRecord[];
  skills: ApiRecord[];
  tools: ApiRecord[];
  workflows: ApiRecord[];
  audit: ApiRecord[];
  events: ApiRecord[];
};

const EMPTY_DATA: DataSet = {
  summary: {}, health: {}, integrity: {}, schema: {}, providers: {}, embeddings: {}, alertStatus: {}, runbooks: [], tasks: [], approvals: [], incidents: [],
  schedules: [], executions: [], queueHealth: {}, agents: [], skills: [], tools: [], workflows: [], audit: [], events: [],
};

const ENDPOINTS: Record<keyof DataSet, string> = {
  summary: "/dashboard/summary",
  health: "/health",
  integrity: "/system/integrity",
  schema: "/database/schema",
  providers: "/models/providers",
  embeddings: "/knowledge/embeddings/status",
  alertStatus: "/alerts/status",
  runbooks: "/runbooks",
  tasks: "/tasks",
  approvals: "/approvals",
  incidents: "/incidents",
  schedules: "/schedules",
  executions: "/scheduler/executions",
  queueHealth: "/scheduler/queue-health",
  agents: "/agents",
  skills: "/skills",
  tools: "/tools",
  workflows: "/workflows",
  audit: "/audit-logs",
  events: "/events?limit=100",
};

const NAV_ITEMS: Array<{ id: View; label: string; icon: typeof Activity }> = [
  { id: "overview", label: "Overview", icon: CircleGauge },
  { id: "work", label: "Work queue", icon: ListChecks },
  { id: "scheduler", label: "Scheduler", icon: CalendarClock },
  { id: "catalog", label: "Catalog", icon: Boxes },
  { id: "governance", label: "Governance", icon: ShieldCheck },
  { id: "system", label: "System", icon: ServerCog },
];

export function OperationsConsole() {
  const [view, setView] = useState<View>("overview");
  const [data, setData] = useState<DataSet>(EMPTY_DATA);
  const [apiBase, setApiBase] = useState(
    process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000",
  );
  const [apiDraft, setApiDraft] = useState(apiBase);
  const [apiToken, setApiToken] = useState(process.env.NEXT_PUBLIC_API_BEARER_TOKEN ?? "");
  const [apiTokenDraft, setApiTokenDraft] = useState(apiToken);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const stored = window.localStorage.getItem("ai-company-os-api-base");
    if (stored) {
      setApiBase(stored);
      setApiDraft(stored);
    }
    const storedToken = getStoredApiToken();
    if (storedToken) {
      setApiToken(storedToken);
      setApiTokenDraft(storedToken);
    }
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    const entries = Object.entries(ENDPOINTS) as Array<[keyof DataSet, string]>;
    const results = await Promise.allSettled(
      entries.map(([, path]) => apiRequest<ApiRecord | ApiRecord[]>(apiBase, path, {}, apiToken)),
    );
    const next = { ...EMPTY_DATA };
    const failures: string[] = [];
    results.forEach((result, index) => {
      const [key] = entries[index];
      if (result.status === "fulfilled") {
        Object.assign(next, { [key]: result.value });
      } else {
        failures.push(`${key}: ${result.reason instanceof Error ? result.reason.message : "request failed"}`);
      }
    });
    setData(next);
    if (failures.length) setError(failures.join(" | "));
    setLoading(false);
  }, [apiBase, apiToken]);

  useEffect(() => { void refresh(); }, [refresh]);

  const mutate = useCallback(async <T,>(path: string, body?: ApiRecord) => {
    setNotice(null);
    setError(null);
    const result = await apiRequest<T>(apiBase, path, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
    }, apiToken);
    await refresh();
    return result;
  }, [apiBase, apiToken, refresh]);

  const saveApiBase = (event: FormEvent) => {
    event.preventDefault();
    const next = apiDraft.trim().replace(/\/$/, "");
    if (!/^https?:\/\//.test(next)) {
      setError("API Base must start with http:// or https://");
      return;
    }
    window.localStorage.setItem("ai-company-os-api-base", next);
    setApiBase(next);
  };

  const saveApiToken = (event: FormEvent) => {
    event.preventDefault();
    const next = apiTokenDraft.trim();
    storeApiToken(next);
    setApiToken(next);
    setNotice(next ? "API bearer token saved for this browser." : "API bearer token cleared.");
  };

  const pendingApprovals = data.approvals.filter((item) => ["pending", "need_more_info"].includes(text(item.status, "")));
  const openIncidents = data.incidents.filter((item) => text(item.status, "") !== "resolved");

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileOpen ? "open" : ""}`}>
        <div className="brand-block">
          <div className="brand-mark">AC</div>
          <div><strong>AI Company OS</strong><span>Human Root Console</span></div>
          <button className="icon-button mobile-close" onClick={() => setMobileOpen(false)} aria-label="Close navigation"><X /></button>
        </div>
        <nav aria-label="Primary navigation">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <button key={item.id} className={view === item.id ? "active" : ""} onClick={() => { setView(item.id); setMobileOpen(false); }}>
                <Icon /><span>{item.label}</span><ChevronRight className="nav-chevron" />
              </button>
            );
          })}
        </nav>
        <div className="sidebar-foot">
          <span className={`health-dot ${error ? "bad" : ""}`} />
          <div><strong>{error ? "API degraded" : "API connected"}</strong><span>{apiBase}</span></div>
        </div>
      </aside>

      <main>
        <header className="topbar">
          <div className="title-row">
            <button className="icon-button mobile-menu" onClick={() => setMobileOpen(true)} aria-label="Open navigation"><Menu /></button>
            <div><p className="eyebrow">Human Root / {NAV_ITEMS.find((item) => item.id === view)?.label}</p><h1>{NAV_ITEMS.find((item) => item.id === view)?.label}</h1></div>
          </div>
          <div className="top-actions">
            <StatusPill value={text(data.integrity.status, loading ? "loading" : "unknown")} />
            <button className="button secondary" onClick={() => void refresh()} disabled={loading}><RefreshCw className={loading ? "spin" : ""} />Refresh</button>
          </div>
        </header>

        {error && <div className="banner error"><AlertTriangle /><span>{error}</span><button onClick={() => setError(null)} aria-label="Dismiss error"><X /></button></div>}
        {notice && <div className="banner success"><Check /><span>{notice}</span><button onClick={() => setNotice(null)} aria-label="Dismiss message"><X /></button></div>}

        {loading && Object.keys(data.summary).length === 0 ? <LoadingState /> : (
          <>
            {view === "overview" && <Overview data={data} pending={pendingApprovals.length} incidents={openIncidents.length} />}
            {view === "work" && <WorkView data={data} mutate={mutate} notify={setNotice} fail={setError} />}
            {view === "scheduler" && <SchedulerView data={data} mutate={mutate} notify={setNotice} fail={setError} />}
            {view === "catalog" && <CatalogView data={data} />}
            {view === "governance" && <GovernanceView data={data} mutate={mutate} notify={setNotice} fail={setError} />}
            {view === "system" && <SystemView data={data} apiDraft={apiDraft} setApiDraft={setApiDraft} saveApiBase={saveApiBase} apiTokenDraft={apiTokenDraft} setApiTokenDraft={setApiTokenDraft} saveApiToken={saveApiToken} hasApiToken={Boolean(apiToken)} />}
          </>
        )}
      </main>
    </div>
  );
}

function Overview({ data, pending, incidents }: { data: DataSet; pending: number; incidents: number }) {
  const s = data.summary;
  const metrics = [
    ["Tasks", s.task_count, ListChecks], ["Pending approvals", pending, ClipboardCheck],
    ["Open incidents", incidents, AlertTriangle], ["Active schedules", s.active_scheduled_job_count, CalendarClock],
    ["Workflow runs", s.workflow_run_count, Workflow], ["Agents", s.agent_count, Bot],
    ["Model tokens", s.model_token_count, Activity], ["Integrity issues", s.integrity_issue_count, ShieldCheck],
  ] as const;
  return (
    <div className="view-stack">
      <section className="metrics-grid">
        {metrics.map(([label, value, Icon]) => <Metric key={label} label={label} value={text(value, "0")} icon={<Icon />} />)}
      </section>
      <section className="two-column">
        <Panel title="Recent work" meta={`${data.tasks.length} total`}>
          <EntityList items={data.tasks.slice(-8).reverse()} empty="No tasks yet." render={(item) => <EntityRow title={text(item.title)} detail={shortId(item.task_id)} status={text(item.status)} />} />
        </Panel>
        <Panel title="Attention queue" meta={`${pending + incidents} open`}>
          <EntityList items={[...data.approvals.filter((a) => text(a.status) === "pending"), ...data.incidents.filter((i) => text(i.status) !== "resolved")].slice(0, 8)} empty="Nothing requires attention." render={(item) => <EntityRow title={text(item.title ?? item.request)} detail={shortId(item.approval_id ?? item.incident_id)} status={text(item.status)} />} />
        </Panel>
      </section>
      <section className="two-column">
        <Panel title="Schedule activity" meta={`${data.executions.length} executions`}>
          <EntityList items={data.executions.slice(-6).reverse()} empty="No scheduled executions." render={(item) => <EntityRow title={shortId(item.schedule_id)} detail={formatDate(item.started_at)} status={text(item.status)} />} />
        </Panel>
        <Panel title="Recent domain events" meta={`${data.events.length} loaded`}>
          <EntityList items={data.events.slice(-6).reverse()} empty="No domain events." render={(item) => <EntityRow title={text(item.event_type)} detail={`${text(item.source_type)} / ${shortId(item.source_id)}`} status={formatDate(item.created_at)} />} />
        </Panel>
      </section>
    </div>
  );
}

type Mutate = <T>(path: string, body?: ApiRecord) => Promise<T>;

function WorkView({ data, mutate, notify, fail }: { data: DataSet; mutate: Mutate; notify: (v: string) => void; fail: (v: string) => void }) {
  const [workflowId, setWorkflowId] = useState("document_generation_v1");
  const [title, setTitle] = useState("Internal operating note");
  const [description, setDescription] = useState("Create a safe internal operating note for AI Company OS.");
  const [input, setInput] = useState("{}");
  const [submitting, setSubmitting] = useState(false);
  const runWorkflow = async (event: FormEvent) => {
    event.preventDefault(); setSubmitting(true);
    try {
      const parsed = JSON.parse(input) as ApiRecord;
      const result = await mutate<ApiRecord>("/workflows/run", { workflow_id: workflowId, title, description, input: parsed });
      notify(`Workflow accepted: ${shortId((result.task as ApiRecord | undefined)?.task_id)}`);
    } catch (error) { fail(error instanceof Error ? error.message : "Workflow failed"); }
    finally { setSubmitting(false); }
  };
  const decide = async (id: unknown, decision: "approve" | "reject") => {
    try {
      await mutate(`/approvals/${text(id)}/${decision}`, { status: decision === "approve" ? "approved" : "rejected", decided_by: "human_root", note: `${decision}d from console` });
      notify(`Approval ${decision === "approve" ? "approved" : "rejected"}.`);
    } catch (error) { fail(error instanceof Error ? error.message : "Decision failed"); }
  };
  return (
    <div className="view-stack">
      <section className="two-column work-layout">
        <Panel title="Run workflow" meta="Controlled execution">
          <form className="form-grid" onSubmit={runWorkflow}>
            <Field label="Workflow"><select value={workflowId} onChange={(e) => setWorkflowId(e.target.value)}>{data.workflows.map((w) => <option key={text(w.workflow_id)} value={text(w.workflow_id)}>{text(w.name ?? w.workflow_id)}</option>)}</select></Field>
            <Field label="Title"><input value={title} onChange={(e) => setTitle(e.target.value)} required /></Field>
            <Field label="Description"><textarea value={description} onChange={(e) => setDescription(e.target.value)} required /></Field>
            <Field label="Workflow input (JSON)"><textarea className="code-input" value={input} onChange={(e) => setInput(e.target.value)} /></Field>
            <button className="button" disabled={submitting}><Play />{submitting ? "Running..." : "Create and run"}</button>
          </form>
        </Panel>
        <Panel title="Approval queue" meta={`${data.approvals.length} total`}>
          <EntityList items={data.approvals.slice().reverse()} empty="No approvals." render={(item) => {
            const pending = ["pending", "need_more_info"].includes(text(item.status, ""));
            const request = item.request as ApiRecord | undefined;
            return <div className="action-row"><EntityRow title={text(request?.action, "Approval request")} detail={`${shortId(item.approval_id)} / ${text(request?.actor_id)}`} status={text(item.status)} />{pending && <div className="inline-actions"><button className="icon-button approve" title="Approve" onClick={() => void decide(item.approval_id, "approve")}><Check /></button><button className="icon-button reject" title="Reject" onClick={() => void decide(item.approval_id, "reject")}><X /></button></div>}</div>;
          }} />
        </Panel>
      </section>
      <Panel title="Tasks" meta={`${data.tasks.length} total`}>
        <div className="table-head"><span>Task</span><span>Status</span><span>Risk</span><span>Result</span></div>
        <EntityList items={data.tasks.slice().reverse()} empty="No tasks." render={(item) => <div className="table-row"><div><strong>{text(item.title)}</strong><span>{shortId(item.task_id)}</span></div><StatusPill value={text(item.status)} /><span>{text(item.risk_level)}</span><span className="truncate">{text(item.result, "No result")}</span></div>} />
      </Panel>
    </div>
  );
}

function SchedulerView({ data, mutate, notify, fail }: { data: DataSet; mutate: Mutate; notify: (v: string) => void; fail: (v: string) => void }) {
  const [name, setName] = useState("Daily operations note");
  const [title, setTitle] = useState("Scheduled operating note");
  const [description, setDescription] = useState("Create the scheduled internal operating note.");
  const [nextRun, setNextRun] = useState(() => new Date(Date.now() + 300000).toISOString().slice(0, 16));
  const create = async (event: FormEvent) => {
    event.preventDefault();
    try {
      await mutate("/schedules", { name, action: "create_task", payload: { title, description }, created_by: "human_root", next_run_at: new Date(nextRun).toISOString(), max_runs: 1 });
      notify("Schedule created.");
    } catch (error) { fail(error instanceof Error ? error.message : "Schedule creation failed"); }
  };
  const control = async (id: unknown, action: string) => {
    const resultLabel: Record<string, string> = { pause: "paused", resume: "resumed", cancel: "cancelled" };
    try { await mutate(`/schedules/${text(id)}/${action}`, { actor_id: "human_root" }); notify(`Schedule ${resultLabel[action] ?? action}.`); }
    catch (error) { fail(error instanceof Error ? error.message : "Schedule update failed"); }
  };
  const queue = data.queueHealth;
  return (
    <div className="view-stack">
      <section className="two-column work-layout">
        <Panel title="Create schedule" meta="One-time task">
          <form className="form-grid" onSubmit={create}>
            <Field label="Schedule name"><input value={name} onChange={(e) => setName(e.target.value)} required /></Field>
            <Field label="Run at"><input type="datetime-local" value={nextRun} onChange={(e) => setNextRun(e.target.value)} required /></Field>
            <Field label="Task title"><input value={title} onChange={(e) => setTitle(e.target.value)} required /></Field>
            <Field label="Task description"><textarea value={description} onChange={(e) => setDescription(e.target.value)} required /></Field>
            <button className="button"><CalendarClock />Create schedule</button>
          </form>
        </Panel>
        <Panel title="Queue health" meta={text(queue.status)}>
          <div className="system-facts">
            <Fact label="Queue" value={text(queue.queue_name)} />
            <Fact label="Workers" value={text(queue.worker_count, "0")} />
            <Fact label="Queued" value={text(queue.queued_count, "0")} />
            <Fact label="Started" value={text(queue.started_count, "0")} />
            <Fact label="Deferred" value={text(queue.deferred_count, "0")} />
            <Fact label="Failed" value={text(queue.failed_count, "0")} />
          </div>
          <div className="legacy-note"><Activity /><div><strong>{text(queue.message, "Queue health is not configured.")}</strong><span>Redis/RQ is transport only; PostgreSQL schedule state remains the source of truth.</span></div></div>
        </Panel>
      </section>
      <section className="two-column">
        <Panel title="Execution history" meta={`${data.executions.length} runs`}>
          <EntityList items={data.executions.slice(-12).reverse()} empty="No executions." render={(item) => <EntityRow title={text(item.action)} detail={`${shortId(item.schedule_id)} / ${formatDate(item.started_at)}`} status={text(item.status)} />} />
        </Panel>
        <Panel title="Recent failed executions" meta={`${text(data.summary.failed_scheduled_execution_count, "0")} failed`}>
          <EntityList items={((data.summary.recent_failed_scheduled_executions as ApiRecord[] | undefined) ?? []).slice().reverse()} empty="No failed scheduled executions." render={(item) => <EntityRow title={shortId(item.schedule_id)} detail={text(item.error, "No error")} status={text(item.status)} />} />
        </Panel>
      </section>
      <Panel title="Schedules" meta={`${data.schedules.length} total`}>
        <EntityList items={data.schedules.slice().reverse()} empty="No schedules." render={(item) => <div className="action-row"><EntityRow title={text(item.name)} detail={`${formatDate(item.next_run_at)} / ${text(item.action)}`} status={text(item.status)} /><div className="inline-actions">{text(item.status) === "active" && <button className="small-button" onClick={() => void control(item.schedule_id, "pause")}>Pause</button>}{text(item.status) === "paused" && <button className="small-button" onClick={() => void control(item.schedule_id, "resume")}>Resume</button>}{["active", "paused"].includes(text(item.status)) && <button className="small-button danger-button" onClick={() => void control(item.schedule_id, "cancel")}>Cancel</button>}</div></div>} />
      </Panel>
    </div>
  );
}

function CatalogView({ data }: { data: DataSet }) {
  const [query, setQuery] = useState("");
  const q = query.toLowerCase();
  const filter = (items: ApiRecord[]) => items.filter((item) => JSON.stringify(item).toLowerCase().includes(q));
  return <div className="view-stack"><div className="search-box"><Search /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search agents, skills, tools, and workflows" /></div><section className="catalog-grid"><Panel title="Agents" meta={`${data.agents.length}`}><EntityList items={filter(data.agents)} empty="No matching agents." render={(item) => <EntityRow title={text(item.name)} detail={`${text(item.department)} / ${shortId(item.agent_id)}`} status={item.enabled === false ? "disabled" : "enabled"} />} /></Panel><Panel title="Skills" meta={`${data.skills.length}`}><EntityList items={filter(data.skills)} empty="No matching skills." render={(item) => <EntityRow title={text(item.name)} detail={`${text(item.type)} / ${shortId(item.skill_id)}`} status={text(item.risk_level)} />} /></Panel><Panel title="Tools" meta={`${data.tools.length}`}><EntityList items={filter(data.tools)} empty="No matching tools." render={(item) => <EntityRow title={text(item.name)} detail={`${text(item.type)} / ${shortId(item.tool_id)}`} status={text(item.risk_level)} />} /></Panel><Panel title="Workflows" meta={`${data.workflows.length}`}><EntityList items={filter(data.workflows)} empty="No matching workflows." render={(item) => <EntityRow title={text(item.name)} detail={shortId(item.workflow_id)} status={text(item.execution_mode)} />} /></Panel></section></div>;
}

function GovernanceView({ data, mutate, notify, fail }: { data: DataSet; mutate: Mutate; notify: (v: string) => void; fail: (v: string) => void }) {
  const updateIncident = async (id: unknown, action: "acknowledge" | "resolve") => {
    try { await mutate(`/incidents/${text(id)}/${action}`, { actor_id: "human_root", note: `${action}d from console` }); notify(`Incident ${action}d.`); }
    catch (error) { fail(error instanceof Error ? error.message : "Incident update failed"); }
  };
  return <div className="view-stack"><section className="two-column"><Panel title="Incidents" meta={`${data.incidents.length} total`}><EntityList items={data.incidents.slice().reverse()} empty="No incidents." render={(item) => <IncidentItem item={item} updateIncident={updateIncident} />} /></Panel><Panel title="Runbooks" meta={`${data.runbooks.length} ready`}><EntityList items={data.runbooks} empty="No runbooks." render={(item) => <EntityRow title={text(item.title)} detail={`${text(item.owner_agent)} / ${text(item.severity)}`} status={shortId(item.runbook_id)} />} /></Panel></section><section className="two-column"><Panel title="Integrity checks" meta={text(data.integrity.status)}><EntityList items={(data.integrity.checks as ApiRecord[] | undefined) ?? []} empty="No integrity checks." render={(item) => <EntityRow title={text(item.name)} detail={text(item.message)} status={text(item.status)} />} /></Panel><Panel title="Audit log" meta={`${data.audit.length} records`}><EntityList items={data.audit.slice(-30).reverse()} empty="No audit records." render={(item) => <EntityRow title={text(item.event_type)} detail={`${text(item.actor_id)} / ${formatDate(item.created_at)}`} status={text(item.risk_level)} />} /></Panel></section><Panel title="Domain events" meta={`${data.events.length} records`}><EntityList items={data.events.slice(-30).reverse()} empty="No domain events." render={(item) => <EntityRow title={text(item.event_type)} detail={`${text(item.source_type)} / ${shortId(item.source_id)}`} status={formatDate(item.created_at)} />} /></Panel></div>;
}

function IncidentItem({ item, updateIncident }: { item: ApiRecord; updateIncident: (id: unknown, action: "acknowledge" | "resolve") => Promise<void> }) {
  const runbook = item.runbook as ApiRecord | undefined;
  const actions = (runbook?.immediate_actions as string[] | undefined) ?? [];
  return <div className="action-row"><div className="incident-detail"><EntityRow title={text(item.title)} detail={`${shortId(item.incident_id)} / ${text(item.risk_level)} / ${text(item.runbook_title, "No runbook")}`} status={text(item.status)} />{runbook && <span className="muted-line">{text(runbook.title)}: {actions[0] ?? text(runbook.description)}</span>}</div>{text(item.status) !== "resolved" && <div className="inline-actions">{text(item.status) === "open" && <button className="small-button" onClick={() => void updateIncident(item.incident_id, "acknowledge")}>Acknowledge</button>}<button className="small-button" onClick={() => void updateIncident(item.incident_id, "resolve")}>Resolve</button></div>}</div>;
}

function SystemView({ data, apiDraft, setApiDraft, saveApiBase, apiTokenDraft, setApiTokenDraft, saveApiToken, hasApiToken }: { data: DataSet; apiDraft: string; setApiDraft: (v: string) => void; saveApiBase: (e: FormEvent) => void; apiTokenDraft: string; setApiTokenDraft: (v: string) => void; saveApiToken: (e: FormEvent) => void; hasApiToken: boolean }) {
  const migrations = (data.schema.migrations as ApiRecord[] | undefined) ?? [];
  return <div className="view-stack"><section className="two-column work-layout"><Panel title="API connection" meta={text(data.health.status)}><form className="form-grid" onSubmit={saveApiBase}><Field label="API Base"><input value={apiDraft} onChange={(e) => setApiDraft(e.target.value)} /></Field><button className="button"><SlidersHorizontal />Apply connection</button></form><form className="form-grid compact-form" onSubmit={saveApiToken}><Field label="Bearer token"><input type="password" value={apiTokenDraft} onChange={(e) => setApiTokenDraft(e.target.value)} placeholder="Required when API auth is enabled" /></Field><button className="button secondary"><ShieldCheck />{hasApiToken ? "Update token" : "Save token"}</button></form></Panel><Panel title="Persistence" meta={text(data.schema.backend)}><div className="system-facts"><Fact label="Backend" value={text(data.schema.backend)} /><Fact label="Schema version" value={text(data.schema.schema_version)} /><Fact label="Integrity" value={text(data.integrity.status)} /><Fact label="Migration count" value={String(migrations.length)} /></div></Panel></section><Panel title="AI providers" meta={text(data.providers.default_provider)}><div className="system-facts"><Fact label="Model provider" value={text(data.providers.default_provider)} /><Fact label="Default model" value={text(data.providers.default_model)} /><Fact label="Embeddings" value={data.embeddings.enabled ? "enabled" : "disabled"} /><Fact label="Embedding model" value={text(data.embeddings.default_model, "not configured")} /><Fact label="Vector dimensions" value={text(data.embeddings.dimensions)} /><Fact label="Indexed documents" value={text(data.embeddings.indexed_documents, "0")} /><Fact label="Failed documents" value={text(data.embeddings.failed_documents, "0")} /><Fact label="Vector store" value={data.embeddings.vector_store ? "connected" : "not connected"} /></div></Panel><Panel title="Alert delivery" meta={data.alertStatus.enabled ? "enabled" : "disabled"}><div className="system-facts"><Fact label="Configured" value={data.alertStatus.configured ? "yes" : "no"} /><Fact label="Destination" value={text(data.alertStatus.destination, "none")} /><Fact label="Endpoint host" value={text(data.alertStatus.endpoint_host, "not configured")} /><Fact label="Timeout" value={`${text(data.alertStatus.timeout_seconds, "5")}s`} /></div></Panel><Panel title="Schema migrations" meta={`${migrations.length} applied`}><EntityList items={migrations} empty="No database migrations reported." render={(item) => <EntityRow title={`${text(item.version)} / ${text(item.migration_id)}`} detail={text(item.description)} status={formatDate(item.applied_at)} />} /></Panel><div className="legacy-note"><FileClock /><div><strong>Legacy console retained</strong><span>The dependency-free dashboard remains available at <code>apps/web_dashboard</code>.</span></div></div></div>;
}

function Panel({ title, meta, children }: { title: string; meta?: string; children: ReactNode }) { return <section className="panel"><div className="panel-heading"><div><h2>{title}</h2>{meta && <span>{meta}</span>}</div></div>{children}</section>; }
function Metric({ label, value, icon }: { label: string; value: string; icon: ReactNode }) { return <div className="metric"><div className="metric-icon">{icon}</div><span>{label}</span><strong>{value}</strong></div>; }
function Field({ label, children }: { label: string; children: ReactNode }) { return <label className="field"><span>{label}</span>{children}</label>; }
function Fact({ label, value }: { label: string; value: string }) { return <div className="fact"><span>{label}</span><strong>{value}</strong></div>; }
function EntityList({ items, empty, render }: { items: ApiRecord[]; empty: string; render: (item: ApiRecord) => ReactNode }) { return items.length ? <div className="entity-list">{items.map((item, index) => <div className="entity-item" key={text(item.id ?? item.task_id ?? item.approval_id ?? item.incident_id ?? item.runbook_id ?? item.schedule_id ?? item.event_id ?? index)}>{render(item)}</div>)}</div> : <EmptyState message={empty} />; }
function EntityRow({ title, detail, status }: { title: string; detail: string; status: string }) { return <div className="entity-row"><div><strong>{title}</strong><span>{detail}</span></div><StatusPill value={status} /></div>; }
function StatusPill({ value }: { value: string }) { const tone = useMemo(() => statusTone(value), [value]); return <span className={`status ${tone}`}>{value.replaceAll("_", " ")}</span>; }
function EmptyState({ message }: { message: string }) { return <div className="empty-state"><Boxes /><span>{message}</span></div>; }
function LoadingState() { return <div className="loading-state"><RefreshCw className="spin" /><strong>Loading operations data</strong><span>Connecting to the AI Company OS API.</span></div>; }
function statusTone(value: string) { const v = value.toLowerCase(); if (["ok", "completed", "approved", "enabled", "active", "verified", "executed"].includes(v)) return "good"; if (["failed", "blocked", "rejected", "critical", "forbidden", "cancelled", "open"].includes(v)) return "bad"; if (["pending", "warning", "waiting_approval", "medium", "paused", "need_more_info"].includes(v)) return "warn"; return "neutral"; }
