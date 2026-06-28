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
import { ApiRecord, apiRequest, formatDate, formatValue, getStoredApiToken, shortId, storeApiToken, text } from "@/lib/api";

type View = "overview" | "work" | "scheduler" | "catalog" | "governance" | "system";
type DataSet = {
  summary: ApiRecord;
  health: ApiRecord;
  readiness: ApiRecord;
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
  summary: {}, health: {}, readiness: {}, integrity: {}, schema: {}, providers: {}, embeddings: {}, alertStatus: {}, runbooks: [], tasks: [], approvals: [], incidents: [],
  schedules: [], executions: [], queueHealth: {}, agents: [], skills: [], tools: [], workflows: [], audit: [], events: [],
};

const ENDPOINTS: Record<keyof DataSet, string> = {
  summary: "/dashboard/summary",
  health: "/health",
  readiness: "/deployment/readiness",
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
  { id: "overview", label: "总览", icon: CircleGauge },
  { id: "work", label: "工作台", icon: ListChecks },
  { id: "scheduler", label: "计划任务", icon: CalendarClock },
  { id: "catalog", label: "能力目录", icon: Boxes },
  { id: "governance", label: "治理中心", icon: ShieldCheck },
  { id: "system", label: "系统设置", icon: ServerCog },
];

const DATA_LABELS: Record<keyof DataSet, string> = {
  summary: "总览",
  health: "服务健康",
  readiness: "生产就绪",
  integrity: "系统完整性",
  schema: "数据库结构",
  providers: "模型服务",
  embeddings: "向量索引",
  alertStatus: "告警状态",
  runbooks: "处置手册",
  tasks: "任务",
  approvals: "审批",
  incidents: "事件",
  schedules: "计划任务",
  executions: "执行记录",
  queueHealth: "队列健康",
  agents: "智能体",
  skills: "技能",
  tools: "工具",
  workflows: "工作流",
  audit: "审计日志",
  events: "领域事件",
};

const CATALOG_LABELS: Record<string, string> = {
  ceo_agent_v1: "AI 首席执行官",
  project_manager_agent_v1: "项目经理智能体",
  document_agent_v1: "文档智能体",
  risk_agent_v1: "风险智能体",
  quality_agent_v1: "质量检查智能体",
  product_agent_v1: "产品智能体",
  tech_agent_v1: "技术智能体",
  data_agent_v1: "数据智能体",
  legal_compliance_agent_v1: "法律与合规智能体",
  finance_assistant_agent_v1: "财务助理智能体",
  memory_agent_v1: "记忆智能体",
  skill_manager_agent_v1: "技能管理员智能体",
  workflow_agent_v1: "工作流智能体",
  audit_agent_v1: "审计智能体",
  capability_gap_detector_agent_v1: "能力缺口检测智能体",
  agent_factory_agent_v1: "智能体工厂智能体",
  skill_factory_agent_v1: "技能工厂智能体",
  task_planning_skill_v1: "任务规划技能",
  document_writer_skill_v1: "文档编写技能",
  summary_skill_v1: "内容摘要技能",
  risk_check_skill_v1: "风险检查技能",
  quality_check_skill_v1: "质量检查技能",
  rewrite_skill_v1: "内容改写技能",
  data_cleanup_skill_v1: "数据清理技能",
  spreadsheet_generation_skill_v1: "电子表格生成技能",
  code_generation_skill_v1: "代码生成技能",
  code_review_skill_v1: "代码审查技能",
  github_project_analysis_skill_v1: "GitHub 项目分析技能",
  approval_request_skill_v1: "审批申请技能",
  audit_logging_skill_v1: "审计记录技能",
  memory_write_skill_v1: "记忆写入技能",
  knowledge_search_skill_v1: "知识搜索技能",
  skill_search_skill_v1: "技能搜索技能",
  skill_composition_skill_v1: "技能组合技能",
  temporary_skill_creation_skill_v1: "临时技能创建技能",
  task_manager_tool: "任务管理工具",
  knowledge_base_tool: "知识库工具",
  audit_read_tool: "审计读取工具",
  database_read_tool: "数据库读取工具",
  filesystem_read_tool: "文件系统读取工具",
  external_api_tool: "外部 API 工具",
  code_execution_tool: "代码执行工具",
  document_generation_v1: "文档生成",
  task_planning_v1: "任务规划",
  agent_collaboration_v1: "智能体协作",
  skill_missing_v1: "缺失技能处理",
  agent_missing_v1: "缺失智能体处理",
  approval_v1: "审批处理",
  quality_check_v1: "质量检查",
  retrospective_v1: "任务复盘",
  github_project_analysis_v1: "GitHub 项目分析",
  tool_call_v1: "工具调用",
};

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
        failures.push(`${DATA_LABELS[key]}：${result.reason instanceof Error ? result.reason.message : "请求失败"}`);
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
      setError("API 地址必须以 http:// 或 https:// 开头");
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
    setNotice(next ? "API 访问令牌已保存到当前浏览器。" : "API 访问令牌已清除。");
  };

  const pendingApprovals = data.approvals.filter((item) => ["pending", "need_more_info"].includes(text(item.status, "")));
  const openIncidents = data.incidents.filter((item) => text(item.status, "") !== "resolved");

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileOpen ? "open" : ""}`}>
        <div className="brand-block">
          <div className="brand-mark">AC</div>
          <div><strong>AI Company OS</strong><span>人类最高管理员控制台</span></div>
          <button className="icon-button mobile-close" onClick={() => setMobileOpen(false)} aria-label="关闭导航"><X /></button>
        </div>
        <nav aria-label="主导航">
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
          <div><strong>{error ? "API 部分异常" : "API 已连接"}</strong><span>{apiBase}</span></div>
        </div>
      </aside>

      <main>
        <header className="topbar">
          <div className="title-row">
            <button className="icon-button mobile-menu" onClick={() => setMobileOpen(true)} aria-label="打开导航"><Menu /></button>
            <div><p className="eyebrow">人类最高管理员 / {NAV_ITEMS.find((item) => item.id === view)?.label}</p><h1>{NAV_ITEMS.find((item) => item.id === view)?.label}</h1></div>
          </div>
          <div className="top-actions">
            <StatusPill value={text(data.integrity.status, loading ? "loading" : "unknown")} />
            <button className="button secondary" onClick={() => void refresh()} disabled={loading}><RefreshCw className={loading ? "spin" : ""} />刷新</button>
          </div>
        </header>

        {error && <div className="banner error"><AlertTriangle /><span>{error}</span><button onClick={() => setError(null)} aria-label="关闭错误提示"><X /></button></div>}
        {notice && <div className="banner success"><Check /><span>{notice}</span><button onClick={() => setNotice(null)} aria-label="关闭消息"><X /></button></div>}

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
    ["任务", s.task_count, ListChecks], ["待审批", pending, ClipboardCheck],
    ["待处理事件", incidents, AlertTriangle], ["运行中的计划", s.active_scheduled_job_count, CalendarClock],
    ["工作流运行", s.workflow_run_count, Workflow], ["智能体", s.agent_count, Bot],
    ["模型令牌", s.model_token_count, Activity], ["完整性问题", s.integrity_issue_count, ShieldCheck],
  ] as const;
  return (
    <div className="view-stack">
      <section className="metrics-grid">
        {metrics.map(([label, value, Icon]) => <Metric key={label} label={label} value={text(value, "0")} icon={<Icon />} />)}
      </section>
      <section className="two-column">
        <Panel title="近期工作" meta={`共 ${data.tasks.length} 项`}>
          <EntityList items={data.tasks.slice(-8).reverse()} empty="暂无任务。" render={(item) => <EntityRow title={text(item.title)} detail={shortId(item.task_id)} status={text(item.status)} />} />
        </Panel>
        <Panel title="待办队列" meta={`${pending + incidents} 项待处理`}>
          <EntityList items={[...data.approvals.filter((a) => text(a.status) === "pending"), ...data.incidents.filter((i) => text(i.status) !== "resolved")].slice(0, 8)} empty="当前没有需要处理的事项。" render={(item) => <EntityRow title={text(item.title ?? item.request)} detail={shortId(item.approval_id ?? item.incident_id)} status={text(item.status)} />} />
        </Panel>
      </section>
      <section className="two-column">
        <Panel title="计划执行动态" meta={`${data.executions.length} 次执行`}>
          <EntityList items={data.executions.slice(-6).reverse()} empty="暂无计划执行记录。" render={(item) => <EntityRow title={shortId(item.schedule_id)} detail={formatDate(item.started_at)} status={text(item.status)} />} />
        </Panel>
        <Panel title="近期领域事件" meta={`已加载 ${data.events.length} 条`}>
          <EntityList items={data.events.slice(-6).reverse()} empty="暂无领域事件。" render={(item) => <EntityRow title={formatValue(item.event_type)} detail={`${formatValue(item.source_type)} / ${shortId(item.source_id)}`} status={formatDate(item.created_at)} />} />
        </Panel>
      </section>
    </div>
  );
}

type Mutate = <T>(path: string, body?: ApiRecord) => Promise<T>;

function WorkView({ data, mutate, notify, fail }: { data: DataSet; mutate: Mutate; notify: (v: string) => void; fail: (v: string) => void }) {
  const [workflowId, setWorkflowId] = useState("document_generation_v1");
  const [title, setTitle] = useState("内部运营说明");
  const [description, setDescription] = useState("为 AI Company OS 创建一份安全的内部运营说明。");
  const [input, setInput] = useState("{}");
  const [submitting, setSubmitting] = useState(false);
  const runWorkflow = async (event: FormEvent) => {
    event.preventDefault(); setSubmitting(true);
    try {
      const parsed = JSON.parse(input) as ApiRecord;
      const result = await mutate<ApiRecord>("/workflows/run", { workflow_id: workflowId, title, description, input: parsed });
      notify(`工作流已受理：${shortId((result.task as ApiRecord | undefined)?.task_id)}`);
    } catch (error) { fail(error instanceof Error ? error.message : "工作流运行失败"); }
    finally { setSubmitting(false); }
  };
  const decide = async (id: unknown, decision: "approve" | "reject") => {
    try {
      await mutate(`/approvals/${text(id)}/${decision}`, { status: decision === "approve" ? "approved" : "rejected", decided_by: "human_root", note: decision === "approve" ? "由控制台批准" : "由控制台拒绝" });
      notify(decision === "approve" ? "审批已批准。" : "审批已拒绝。");
    } catch (error) { fail(error instanceof Error ? error.message : "审批操作失败"); }
  };
  return (
    <div className="view-stack">
      <section className="two-column work-layout">
        <Panel title="运行工作流" meta="受控执行">
          <form className="form-grid" onSubmit={runWorkflow}>
            <Field label="工作流"><select value={workflowId} onChange={(e) => setWorkflowId(e.target.value)}>{data.workflows.map((w) => <option key={text(w.workflow_id)} value={text(w.workflow_id)}>{workflowName(w)}</option>)}</select></Field>
            <Field label="标题"><input value={title} onChange={(e) => setTitle(e.target.value)} required /></Field>
            <Field label="说明"><textarea value={description} onChange={(e) => setDescription(e.target.value)} required /></Field>
            <Field label="工作流输入（JSON）"><textarea className="code-input" value={input} onChange={(e) => setInput(e.target.value)} /></Field>
            <button className="button" disabled={submitting}><Play />{submitting ? "运行中..." : "创建并运行"}</button>
          </form>
        </Panel>
        <Panel title="审批队列" meta={`共 ${data.approvals.length} 项`}>
          <EntityList items={data.approvals.slice().reverse()} empty="暂无审批。" render={(item) => {
            const pending = ["pending", "need_more_info"].includes(text(item.status, ""));
            const request = item.request as ApiRecord | undefined;
            return <div className="action-row"><EntityRow title={formatValue(request?.action, "审批请求")} detail={`${shortId(item.approval_id)} / ${formatValue(request?.actor_id)}`} status={text(item.status)} />{pending && <div className="inline-actions"><button className="icon-button approve" title="批准" onClick={() => void decide(item.approval_id, "approve")}><Check /></button><button className="icon-button reject" title="拒绝" onClick={() => void decide(item.approval_id, "reject")}><X /></button></div>}</div>;
          }} />
        </Panel>
      </section>
      <Panel title="任务" meta={`共 ${data.tasks.length} 项`}>
        <div className="table-head"><span>任务</span><span>状态</span><span>风险</span><span>结果</span></div>
        <EntityList items={data.tasks.slice().reverse()} empty="暂无任务。" render={(item) => <div className="table-row"><div><strong>{text(item.title)}</strong><span>{shortId(item.task_id)}</span></div><StatusPill value={text(item.status)} /><span>{formatValue(item.risk_level)}</span><span className="truncate">{text(item.result, "暂无结果")}</span></div>} />
      </Panel>
    </div>
  );
}

function SchedulerView({ data, mutate, notify, fail }: { data: DataSet; mutate: Mutate; notify: (v: string) => void; fail: (v: string) => void }) {
  const [name, setName] = useState("每日运营说明");
  const [title, setTitle] = useState("计划运营说明");
  const [description, setDescription] = useState("创建计划中的内部运营说明。");
  const [nextRun, setNextRun] = useState(() => new Date(Date.now() + 300000).toISOString().slice(0, 16));
  const create = async (event: FormEvent) => {
    event.preventDefault();
    try {
      await mutate("/schedules", { name, action: "create_task", payload: { title, description }, created_by: "human_root", next_run_at: new Date(nextRun).toISOString(), max_runs: 1 });
      notify("计划任务已创建。");
    } catch (error) { fail(error instanceof Error ? error.message : "计划任务创建失败"); }
  };
  const control = async (id: unknown, action: string) => {
    const resultLabel: Record<string, string> = { pause: "计划任务已暂停。", resume: "计划任务已恢复。", cancel: "计划任务已取消。" };
    try { await mutate(`/schedules/${text(id)}/${action}`, { actor_id: "human_root" }); notify(resultLabel[action] ?? "计划任务已更新。"); }
    catch (error) { fail(error instanceof Error ? error.message : "计划任务更新失败"); }
  };
  const queue = data.queueHealth;
  return (
    <div className="view-stack">
      <section className="two-column work-layout">
        <Panel title="创建计划任务" meta="单次任务">
          <form className="form-grid" onSubmit={create}>
            <Field label="计划名称"><input value={name} onChange={(e) => setName(e.target.value)} required /></Field>
            <Field label="运行时间"><input type="datetime-local" value={nextRun} onChange={(e) => setNextRun(e.target.value)} required /></Field>
            <Field label="任务标题"><input value={title} onChange={(e) => setTitle(e.target.value)} required /></Field>
            <Field label="任务说明"><textarea value={description} onChange={(e) => setDescription(e.target.value)} required /></Field>
            <button className="button"><CalendarClock />创建计划任务</button>
          </form>
        </Panel>
        <Panel title="队列健康" meta={formatValue(queue.status)}>
          <div className="system-facts">
            <Fact label="队列" value={text(queue.queue_name)} />
            <Fact label="工作进程" value={text(queue.worker_count, "0")} />
            <Fact label="排队中" value={text(queue.queued_count, "0")} />
            <Fact label="已开始" value={text(queue.started_count, "0")} />
            <Fact label="已延后" value={text(queue.deferred_count, "0")} />
            <Fact label="失败" value={text(queue.failed_count, "0")} />
          </div>
          <div className="legacy-note"><Activity /><div><strong>{queue.status === "not_configured" ? "尚未配置队列健康检查。" : text(queue.message, "队列状态可用。")}</strong><span>Redis/RQ 仅负责传输；PostgreSQL 中的计划状态仍是唯一事实来源。</span></div></div>
        </Panel>
      </section>
      <section className="two-column">
        <Panel title="执行历史" meta={`${data.executions.length} 次运行`}>
          <EntityList items={data.executions.slice(-12).reverse()} empty="暂无执行记录。" render={(item) => <EntityRow title={formatValue(item.action)} detail={`${shortId(item.schedule_id)} / ${formatDate(item.started_at)}`} status={text(item.status)} />} />
        </Panel>
        <Panel title="近期失败执行" meta={`${text(data.summary.failed_scheduled_execution_count, "0")} 次失败`}>
          <EntityList items={((data.summary.recent_failed_scheduled_executions as ApiRecord[] | undefined) ?? []).slice().reverse()} empty="暂无失败的计划执行。" render={(item) => <EntityRow title={shortId(item.schedule_id)} detail={text(item.error, "没有错误信息")} status={text(item.status)} />} />
        </Panel>
      </section>
      <Panel title="计划任务" meta={`共 ${data.schedules.length} 项`}>
        <EntityList items={data.schedules.slice().reverse()} empty="暂无计划任务。" render={(item) => <div className="action-row"><EntityRow title={text(item.name)} detail={`${formatDate(item.next_run_at)} / ${formatValue(item.action)}`} status={text(item.status)} /><div className="inline-actions">{text(item.status) === "active" && <button className="small-button" onClick={() => void control(item.schedule_id, "pause")}>暂停</button>}{text(item.status) === "paused" && <button className="small-button" onClick={() => void control(item.schedule_id, "resume")}>恢复</button>}{["active", "paused"].includes(text(item.status)) && <button className="small-button danger-button" onClick={() => void control(item.schedule_id, "cancel")}>取消</button>}</div></div>} />
      </Panel>
    </div>
  );
}

function CatalogView({ data }: { data: DataSet }) {
  const [query, setQuery] = useState("");
  const q = query.toLowerCase();
  const filter = (items: ApiRecord[]) => items.filter((item) => JSON.stringify(item).toLowerCase().includes(q));
  return <div className="view-stack"><div className="search-box"><Search /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="搜索智能体、技能、工具和工作流" /></div><section className="catalog-grid"><Panel title="智能体" meta={`${data.agents.length}`}><EntityList items={filter(data.agents)} empty="没有匹配的智能体。" render={(item) => <EntityRow title={agentName(item)} detail={`${formatValue(item.department)} / ${shortId(item.agent_id)}`} status={item.enabled === false ? "disabled" : "enabled"} />} /></Panel><Panel title="技能" meta={`${data.skills.length}`}><EntityList items={filter(data.skills)} empty="没有匹配的技能。" render={(item) => <EntityRow title={catalogName(item, "skill_id")} detail={`${formatValue(item.type)} / ${shortId(item.skill_id)}`} status={text(item.risk_level)} />} /></Panel><Panel title="工具" meta={`${data.tools.length}`}><EntityList items={filter(data.tools)} empty="没有匹配的工具。" render={(item) => <EntityRow title={catalogName(item, "tool_id")} detail={`${formatValue(item.type)} / ${shortId(item.tool_id)}`} status={text(item.risk_level)} />} /></Panel><Panel title="工作流" meta={`${data.workflows.length}`}><EntityList items={filter(data.workflows)} empty="没有匹配的工作流。" render={(item) => <EntityRow title={workflowName(item)} detail={shortId(item.workflow_id)} status={text(item.execution_mode)} />} /></Panel></section></div>;
}

function GovernanceView({ data, mutate, notify, fail }: { data: DataSet; mutate: Mutate; notify: (v: string) => void; fail: (v: string) => void }) {
  const updateIncident = async (id: unknown, action: "acknowledge" | "resolve") => {
    try { await mutate(`/incidents/${text(id)}/${action}`, { actor_id: "human_root", note: action === "acknowledge" ? "由控制台确认" : "由控制台解决" }); notify(action === "acknowledge" ? "事件已确认。" : "事件已解决。"); }
    catch (error) { fail(error instanceof Error ? error.message : "事件更新失败"); }
  };
  return <div className="view-stack"><section className="two-column"><Panel title="事件" meta={`共 ${data.incidents.length} 项`}><EntityList items={data.incidents.slice().reverse()} empty="暂无事件。" render={(item) => <IncidentItem item={item} updateIncident={updateIncident} />} /></Panel><Panel title="处置手册" meta={`${data.runbooks.length} 项可用`}><EntityList items={data.runbooks} empty="暂无处置手册。" render={(item) => <EntityRow title={text(item.title)} detail={`${agentName({ agent_id: item.owner_agent, name: item.owner_agent })} / ${formatValue(item.severity)}`} status={shortId(item.runbook_id)} />} /></Panel></section><section className="two-column"><Panel title="完整性检查" meta={formatValue(data.integrity.status)}><EntityList items={(data.integrity.checks as ApiRecord[] | undefined) ?? []} empty="暂无完整性检查。" render={(item) => <EntityRow title={text(item.name)} detail={text(item.message)} status={text(item.status)} />} /></Panel><Panel title="审计日志" meta={`${data.audit.length} 条记录`}><EntityList items={data.audit.slice(-30).reverse()} empty="暂无审计记录。" render={(item) => <EntityRow title={formatValue(item.event_type)} detail={`${formatValue(item.actor_id)} / ${formatDate(item.created_at)}`} status={text(item.risk_level)} />} /></Panel></section><Panel title="领域事件" meta={`${data.events.length} 条记录`}><EntityList items={data.events.slice(-30).reverse()} empty="暂无领域事件。" render={(item) => <EntityRow title={formatValue(item.event_type)} detail={`${formatValue(item.source_type)} / ${shortId(item.source_id)}`} status={formatDate(item.created_at)} />} /></Panel></div>;
}

function IncidentItem({ item, updateIncident }: { item: ApiRecord; updateIncident: (id: unknown, action: "acknowledge" | "resolve") => Promise<void> }) {
  const runbook = item.runbook as ApiRecord | undefined;
  const actions = (runbook?.immediate_actions as string[] | undefined) ?? [];
  return <div className="action-row"><div className="incident-detail"><EntityRow title={text(item.title)} detail={`${shortId(item.incident_id)} / ${formatValue(item.risk_level)} / ${text(item.runbook_title, "无处置手册")}`} status={text(item.status)} />{runbook && <span className="muted-line">{text(runbook.title)}：{actions[0] ?? text(runbook.description)}</span>}</div>{text(item.status) !== "resolved" && <div className="inline-actions">{text(item.status) === "open" && <button className="small-button" onClick={() => void updateIncident(item.incident_id, "acknowledge")}>确认</button>}<button className="small-button" onClick={() => void updateIncident(item.incident_id, "resolve")}>解决</button></div>}</div>;
}

function SystemView({ data, apiDraft, setApiDraft, saveApiBase, apiTokenDraft, setApiTokenDraft, saveApiToken, hasApiToken }: { data: DataSet; apiDraft: string; setApiDraft: (v: string) => void; saveApiBase: (e: FormEvent) => void; apiTokenDraft: string; setApiTokenDraft: (v: string) => void; saveApiToken: (e: FormEvent) => void; hasApiToken: boolean }) {
  const migrations = (data.schema.migrations as ApiRecord[] | undefined) ?? [];
  const readinessChecks = (data.readiness.checks as ApiRecord[] | undefined) ?? [];
  return (
    <div className="view-stack">
      <section className="two-column work-layout">
        <Panel title="API 连接" meta={formatValue(data.health.status)}>
          <form className="form-grid" onSubmit={saveApiBase}>
            <Field label="API 地址"><input value={apiDraft} onChange={(e) => setApiDraft(e.target.value)} /></Field>
            <button className="button"><SlidersHorizontal />应用连接</button>
          </form>
          <form className="form-grid compact-form" onSubmit={saveApiToken}>
            <Field label="访问令牌"><input type="password" value={apiTokenDraft} onChange={(e) => setApiTokenDraft(e.target.value)} placeholder="启用 API 身份验证时需要填写" /></Field>
            <button className="button secondary"><ShieldCheck />{hasApiToken ? "更新令牌" : "保存令牌"}</button>
          </form>
        </Panel>
        <Panel title="生产就绪检查" meta={formatValue(data.readiness.status, "unknown")}>
          <EntityList items={readinessChecks} empty="没有生产就绪检查结果。" render={(item) => <EntityRow title={text(item.name)} detail={text(item.message)} status={text(item.status)} />} />
        </Panel>
      </section>
      <Panel title="持久化" meta={formatValue(data.schema.backend)}>
        <div className="system-facts">
          <Fact label="后端" value={formatValue(data.schema.backend)} />
          <Fact label="数据库结构版本" value={text(data.schema.schema_version)} />
          <Fact label="完整性" value={formatValue(data.integrity.status)} />
          <Fact label="迁移数量" value={String(migrations.length)} />
        </div>
      </Panel>
      <Panel title="AI 服务" meta={formatValue(data.providers.default_provider)}>
        <div className="system-facts">
          <Fact label="模型服务商" value={formatValue(data.providers.default_provider)} />
          <Fact label="默认模型" value={text(data.providers.default_model)} />
          <Fact label="向量嵌入" value={data.embeddings.enabled ? "已启用" : "已禁用"} />
          <Fact label="嵌入模型" value={text(data.embeddings.default_model, "未配置")} />
          <Fact label="向量维度" value={text(data.embeddings.dimensions)} />
          <Fact label="已索引文档" value={text(data.embeddings.indexed_documents, "0")} />
          <Fact label="失败文档" value={text(data.embeddings.failed_documents, "0")} />
          <Fact label="向量存储" value={data.embeddings.vector_store ? "已连接" : "未连接"} />
        </div>
      </Panel>
      <Panel title="告警发送" meta={data.alertStatus.enabled ? "已启用" : "已禁用"}>
        <div className="system-facts">
          <Fact label="已配置" value={data.alertStatus.configured ? "是" : "否"} />
          <Fact label="发送目标" value={formatValue(data.alertStatus.destination, "none")} />
          <Fact label="端点主机" value={text(data.alertStatus.endpoint_host, "未配置")} />
          <Fact label="超时时间" value={`${text(data.alertStatus.timeout_seconds, "5")} 秒`} />
        </div>
      </Panel>
      <Panel title="数据库结构迁移" meta={`已应用 ${migrations.length} 项`}>
        <EntityList items={migrations} empty="没有数据库迁移记录。" render={(item) => <EntityRow title={`${text(item.version)} / ${text(item.migration_id)}`} detail={text(item.description)} status={formatDate(item.applied_at)} />} />
      </Panel>
      <div className="legacy-note"><FileClock /><div><strong>已保留旧版控制台</strong><span>无依赖的备用控制台仍位于 <code>apps/web_dashboard</code>。</span></div></div>
    </div>
  );
}

function catalogName(item: ApiRecord, idKey: string): string {
  const id = text(item[idKey], "");
  return CATALOG_LABELS[id] ?? text(item.name ?? item[idKey]);
}

function agentName(item: ApiRecord): string {
  return catalogName(item, "agent_id");
}

function workflowName(item: ApiRecord): string {
  return catalogName(item, "workflow_id");
}

function Panel({ title, meta, children }: { title: string; meta?: string; children: ReactNode }) { return <section className="panel"><div className="panel-heading"><div><h2>{title}</h2>{meta && <span>{meta}</span>}</div></div>{children}</section>; }
function Metric({ label, value, icon }: { label: string; value: string; icon: ReactNode }) { return <div className="metric"><div className="metric-icon">{icon}</div><span>{label}</span><strong>{value}</strong></div>; }
function Field({ label, children }: { label: string; children: ReactNode }) { return <label className="field"><span>{label}</span>{children}</label>; }
function Fact({ label, value }: { label: string; value: string }) { return <div className="fact"><span>{label}</span><strong>{value}</strong></div>; }
function EntityList({ items, empty, render }: { items: ApiRecord[]; empty: string; render: (item: ApiRecord) => ReactNode }) { return items.length ? <div className="entity-list">{items.map((item, index) => <div className="entity-item" key={`${text(item.id ?? item.task_id ?? item.approval_id ?? item.incident_id ?? item.runbook_id ?? item.schedule_id ?? item.event_id ?? "record")}-${index}`}>{render(item)}</div>)}</div> : <EmptyState message={empty} />; }
function EntityRow({ title, detail, status }: { title: string; detail: string; status: string }) { return <div className="entity-row"><div><strong>{title}</strong><span>{detail}</span></div><StatusPill value={status} /></div>; }
function StatusPill({ value }: { value: string }) { const tone = useMemo(() => statusTone(value), [value]); return <span className={`status ${tone}`}>{formatValue(value)}</span>; }
function EmptyState({ message }: { message: string }) { return <div className="empty-state"><Boxes /><span>{message}</span></div>; }
function LoadingState() { return <div className="loading-state"><RefreshCw className="spin" /><strong>正在加载运营数据</strong><span>正在连接 AI Company OS API。</span></div>; }
function statusTone(value: string) { const v = value.toLowerCase(); if (["ok", "ready", "completed", "approved", "enabled", "active", "verified", "executed"].includes(v)) return "good"; if (["failed", "blocked", "rejected", "critical", "not_ready", "forbidden", "cancelled", "open"].includes(v)) return "bad"; if (["pending", "warning", "waiting_approval", "medium", "paused", "need_more_info"].includes(v)) return "warn"; return "neutral"; }
