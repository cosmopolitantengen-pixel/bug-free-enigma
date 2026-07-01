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
  MessageSquare,
  Play,
  Plus,
  RefreshCw,
  Search,
  Send,
  ServerCog,
  ShieldCheck,
  SlidersHorizontal,
  Trash2,
  Workflow,
  X,
} from "lucide-react";
import { FormEvent, ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiRecord, apiRequest, formatDate, formatValue, getStoredApiToken, shortId, storeApiToken, text } from "@/lib/api";

type View = "chat" | "overview" | "work" | "scheduler" | "catalog" | "governance" | "system";
type ChatAction = {
  proposalId: string;
  workflowId: string;
  workflowName: string;
  title: string;
  description: string;
  input: ApiRecord;
  purpose: string;
  status: "pending" | "executing" | "waiting_approval" | "deciding" | "completed" | "cancelled" | "failed";
  taskId?: string;
  approvalId?: string;
  riskLevel?: string;
  approvalInput?: ApiRecord;
  runId?: string;
};
type AgentRunStep = {
  id: string;
  sequence: number;
  intent: string;
  status: string;
  taskId?: string;
  observation?: string;
};
type AgentRun = {
  id: string;
  status: string;
  objective: string;
  steps: AgentRunStep[];
  error?: string;
};
type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
  provider?: string;
  model?: string;
  totalTokens?: number;
  cost?: number;
  fallbackUsed?: boolean;
  failed?: boolean;
  action?: ChatAction;
};
type ChatSession = {
  id: string;
  title: string;
  messages: ChatMessage[];
  updatedAt: string;
  agentRuns: AgentRun[];
};
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
  { id: "chat", label: "对话", icon: MessageSquare },
  { id: "overview", label: "总览", icon: CircleGauge },
  { id: "work", label: "工作台", icon: ListChecks },
  { id: "scheduler", label: "计划任务", icon: CalendarClock },
  { id: "catalog", label: "能力目录", icon: Boxes },
  { id: "governance", label: "治理中心", icon: ShieldCheck },
  { id: "system", label: "系统设置", icon: ServerCog },
];

const CHAT_STORAGE_KEY = "ai-company-os-chat-sessions-v1";

function createId(prefix: string) {
  const suffix = typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}-${suffix}`;
}

function chatActionFromApi(value: ApiRecord | undefined): ChatAction | undefined {
  if (!value) return undefined;
  const workflowId = text(value.workflow_id);
  return {
    proposalId: text(value.proposal_id),
    workflowId,
    workflowName: CATALOG_LABELS[workflowId] ?? text(value.workflow_name),
    title: text(value.title),
    description: text(value.description),
    input: (value.input as ApiRecord | undefined) ?? {},
    purpose: text(value.purpose),
    status: text(value.status, "pending") as ChatAction["status"],
    taskId: text(value.task_id, "") || undefined,
    approvalId: text(value.approval_id, "") || undefined,
    riskLevel: text(value.risk_level, "") || undefined,
    approvalInput: (value.approval_input as ApiRecord | undefined) ?? undefined,
    runId: text(value.run_id, "") || undefined,
  };
}

function chatMessageFromApi(value: ApiRecord): ChatMessage {
  return {
    id: text(value.message_id),
    role: text(value.role) as ChatMessage["role"],
    content: text(value.content),
    createdAt: text(value.created_at),
    provider: text(value.provider, "") || undefined,
    model: text(value.model, "") || undefined,
    totalTokens: value.total_tokens == null ? undefined : Number(value.total_tokens),
    cost: value.cost == null ? undefined : Number(value.cost),
    fallbackUsed: value.fallback_used == null ? undefined : Boolean(value.fallback_used),
    failed: Boolean(value.failed),
    action: chatActionFromApi(value.action as ApiRecord | undefined),
  };
}

function chatSessionFromApi(value: ApiRecord): ChatSession {
  return {
    id: text(value.session_id),
    title: text(value.title, "新对话"),
    messages: ((value.messages as ApiRecord[] | undefined) ?? []).map(chatMessageFromApi),
    updatedAt: text(value.updated_at),
    agentRuns: ((value.agent_runs as ApiRecord[] | undefined) ?? []).map((run) => ({
      id: text(run.run_id),
      status: text(run.status),
      objective: text(run.objective),
      error: text(run.error, "") || undefined,
      steps: ((run.steps as ApiRecord[] | undefined) ?? []).map((step) => ({
        id: text(step.step_id),
        sequence: Number(step.sequence),
        intent: text(step.intent),
        status: text(step.status),
        taskId: text(step.task_id, "") || undefined,
        observation: text(step.observation, "") || undefined,
      })),
    })),
  };
}

function chatActionResult(result: ApiRecord): string {
  const toolRun = result.tool_run as ApiRecord | undefined;
  if (typeof toolRun?.result === "string") {
    try {
      const parsed = JSON.parse(toolRun.result) as ApiRecord;
      const direct = parsed.output ?? parsed.stdout ?? parsed.content;
      if (typeof direct === "string" && direct.trim()) return direct.trim().slice(0, 12000);
      return JSON.stringify(parsed, null, 2).slice(0, 12000);
    } catch {
      return toolRun.result.slice(0, 12000);
    }
  }
  return text(result.output, "任务已经完成。");
}

function chatApprovalPreview(action: ChatAction): string {
  const input = action.approvalInput ?? {};
  const diff = text(input.diff_preview, "");
  if (diff) return diff.slice(0, 12000);
  const argv = input.argv;
  if (Array.isArray(argv)) return argv.map((item) => String(item)).join(" ").slice(0, 1000);
  const path = text(input.path, "");
  if (path) return `文件：${path}`;
  return action.purpose;
}

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
  workspace_agent_v1: "工作区智能体",
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
  workspace_patch_tool: "工作区补丁工具",
  workspace_command_tool: "工作区命令工具",
  git_read_tool: "Git 读取工具",
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
  agent_run_v1: "连续 Agent",
};

export function OperationsConsole() {
  const [view, setView] = useState<View>("chat");
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

  const listChatSessions = useCallback(async () => apiRequest<ApiRecord[]>(apiBase, "/chat/sessions", {}, apiToken), [apiBase, apiToken]);

  const createChatSession = useCallback(async () => apiRequest<ApiRecord>(apiBase, "/chat/sessions", {
    method: "POST",
    body: JSON.stringify({ title: "新对话" }),
  }, apiToken), [apiBase, apiToken]);

  const importChatSessions = useCallback(async (sessions: ApiRecord[]) => apiRequest<ApiRecord[]>(apiBase, "/chat/sessions/import", {
    method: "POST",
    body: JSON.stringify({ sessions }),
  }, apiToken), [apiBase, apiToken]);

  const deleteChatSession = useCallback(async (sessionId: string) => apiRequest<ApiRecord>(apiBase, `/chat/sessions/${sessionId}`, {
    method: "DELETE",
  }, apiToken), [apiBase, apiToken]);

  const callChat = useCallback(async (sessionId: string, body: ApiRecord) => apiRequest<ApiRecord>(apiBase, `/chat/sessions/${sessionId}/messages`, {
    method: "POST",
    body: JSON.stringify(body),
  }, apiToken), [apiBase, apiToken]);

  const executeChatAction = useCallback(async (proposalId: string) => {
    const result = await apiRequest<ApiRecord>(apiBase, `/chat/actions/${proposalId}/execute`, {
      method: "POST",
      signal: AbortSignal.timeout(130_000),
    }, apiToken);
    await refresh();
    return result;
  }, [apiBase, apiToken, refresh]);

  const decideChatAction = useCallback(async (taskId: string, decision: "approved" | "rejected") => {
    const result = await apiRequest<ApiRecord>(apiBase, `/tasks/${taskId}/decision`, {
      method: "POST",
      signal: AbortSignal.timeout(130_000),
      body: JSON.stringify({
        status: decision,
        decided_by: "human_root",
        note: decision === "approved" ? "由聊天行动卡批准并续跑" : "由聊天行动卡拒绝执行",
      }),
    }, apiToken);
    await refresh();
    return result;
  }, [apiBase, apiToken, refresh]);

  const cancelChatAction = useCallback(async (proposalId: string) => apiRequest<ApiRecord>(apiBase, `/chat/actions/${proposalId}/cancel`, {
    method: "POST",
  }, apiToken), [apiBase, apiToken]);

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
            {view === "chat" && <ChatView data={data} listChatSessions={listChatSessions} createChatSession={createChatSession} importChatSessions={importChatSessions} deleteChatSession={deleteChatSession} callChat={callChat} executeChatAction={executeChatAction} decideChatAction={decideChatAction} cancelChatAction={cancelChatAction} fail={setError} />}
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

type ChatListCall = () => Promise<ApiRecord[]>;
type ChatCreateCall = () => Promise<ApiRecord>;
type ChatImportCall = (sessions: ApiRecord[]) => Promise<ApiRecord[]>;
type ChatDeleteCall = (sessionId: string) => Promise<ApiRecord>;
type ChatCall = (sessionId: string, body: ApiRecord) => Promise<ApiRecord>;
type ChatActionCall = (proposalId: string) => Promise<ApiRecord>;
type ChatDecisionCall = (taskId: string, decision: "approved" | "rejected") => Promise<ApiRecord>;
type ChatCancelCall = (proposalId: string) => Promise<ApiRecord>;

function ChatView({ data, listChatSessions, createChatSession, importChatSessions, deleteChatSession, callChat, executeChatAction, decideChatAction, cancelChatAction, fail }: { data: DataSet; listChatSessions: ChatListCall; createChatSession: ChatCreateCall; importChatSessions: ChatImportCall; deleteChatSession: ChatDeleteCall; callChat: ChatCall; executeChatAction: ChatActionCall; decideChatAction: ChatDecisionCall; cancelChatAction: ChatCancelCall; fail: (v: string) => void }) {
  const providerNames = (data.providers.providers as string[] | undefined) ?? ["local"];
  const allowedModels = (data.providers.allowed_models as Record<string, string[]> | undefined) ?? {};
  const [provider, setProvider] = useState(() => text(data.providers.default_provider, providerNames[0] ?? "local"));
  const [model, setModel] = useState(() => text(data.providers.default_model, "deterministic_mock_v1"));
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState("");
  const [chatReady, setChatReady] = useState(false);
  const [draft, setDraft] = useState("");
  const [sendingChatId, setSendingChatId] = useState<string | null>(null);
  const [chatMode, setChatMode] = useState<"auto" | "chat" | "action" | "agent">("auto");
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const executingActionIds = useRef<Set<string>>(new Set());
  const availableModels = allowedModels[provider] ?? [];
  const activeSession = sessions.find((session) => session.id === activeSessionId) ?? sessions[0];

  const loadServerSessions = useCallback(async (preferredId?: string) => {
    const records = await listChatSessions();
    const next = records.map(chatSessionFromApi);
    setSessions(next);
    setActiveSessionId((current) => {
      const preferred = preferredId || current;
      return next.some((session) => session.id === preferred) ? preferred : next[0]?.id ?? "";
    });
    return next;
  }, [listChatSessions]);

  useEffect(() => {
    let cancelled = false;
    const initialize = async () => {
      try {
        let records = await listChatSessions();
        if (!records.length) {
          let legacy: ApiRecord[] = [];
          try {
            const stored = window.localStorage.getItem(CHAT_STORAGE_KEY);
            const parsed = stored ? JSON.parse(stored) : [];
            if (Array.isArray(parsed)) {
              legacy = parsed.map((session) => ({
                legacy_id: text(session?.id, ""),
                title: text(session?.title, "导入的对话"),
                messages: Array.isArray(session?.messages)
                  ? session.messages.map((message: ApiRecord) => ({ role: message.role, content: message.content }))
                  : [],
              }));
            }
          } catch {
            legacy = [];
          }
          if (legacy.length) records = await importChatSessions(legacy);
        }
        window.localStorage.removeItem(CHAT_STORAGE_KEY);
        if (!records.length) records = [await createChatSession()];
        if (!cancelled) {
          const next = records.map(chatSessionFromApi);
          setSessions(next);
          setActiveSessionId(next[0].id);
        }
      } catch {
        // The parent console already reports API read failures with endpoint context.
      } finally {
        if (!cancelled) setChatReady(true);
      }
    };
    void initialize();
    return () => { cancelled = true; };
  }, [createChatSession, importChatSessions, listChatSessions]);

  useEffect(() => {
    if (!providerNames.includes(provider)) {
      setProvider(text(data.providers.default_provider, providerNames[0] ?? "local"));
    }
  }, [data.providers.default_provider, provider, providerNames]);

  useEffect(() => {
    const models = allowedModels[provider] ?? [];
    if (models.length && !models.includes(model)) setModel(models[0]);
  }, [allowedModels, model, provider]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ block: "end" });
  }, [activeSession?.messages.length, sendingChatId]);

  const startNewChat = async () => {
    try {
      const next = chatSessionFromApi(await createChatSession());
      setSessions((current) => [next, ...current]);
      setActiveSessionId(next.id);
      setDraft("");
    } catch (error) {
      fail(error instanceof Error ? error.message : "新建对话失败");
    }
  };

  const deleteChat = async (sessionId: string) => {
    try {
      await deleteChatSession(sessionId);
      let next = await loadServerSessions();
      if (!next.length) {
        const created = chatSessionFromApi(await createChatSession());
        next = [created];
        setSessions(next);
        setActiveSessionId(created.id);
      }
    } catch (error) {
      fail(error instanceof Error ? error.message : "删除对话失败");
    }
  };

  const sendMessage = async (event: FormEvent) => {
    event.preventDefault();
    const content = draft.trim();
    if (!content || !activeSession || sendingChatId || !model) return;

    fail("");
    const sessionId = activeSession.id;
    setDraft("");
    setSendingChatId(sessionId);

    try {
      const result = await callChat(sessionId, {
        content,
        mode: chatMode,
        provider,
        model_name: model,
      });
      const serverSession = result.session as ApiRecord | undefined;
      if (serverSession) {
        const next = chatSessionFromApi(serverSession);
        setSessions((current) => [next, ...current.filter((session) => session.id !== next.id)]);
        setActiveSessionId(next.id);
      } else {
        await loadServerSessions(sessionId);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "模型调用失败";
      try { await loadServerSessions(sessionId); } catch { /* Keep the last visible state. */ }
      fail(message);
    } finally {
      setSendingChatId(null);
    }
  };

  const updateAction = (sessionId: string, messageId: string, update: Partial<ChatAction>) => {
    setSessions((current) => current.map((session) => session.id === sessionId ? {
      ...session,
      messages: session.messages.map((message) => message.id === messageId && message.action ? {
        ...message,
        action: { ...message.action, ...update },
      } : message),
      updatedAt: new Date().toISOString(),
    } : session));
  };

  const executeAction = async (message: ChatMessage) => {
    if (!activeSession || !message.action || message.action.status !== "pending" || executingActionIds.current.has(message.action.proposalId)) return;
    const sessionId = activeSession.id;
    const action = message.action;
    executingActionIds.current.add(action.proposalId);
    updateAction(sessionId, message.id, { status: "executing" });
    try {
      const result = await executeChatAction(action.proposalId);
      const serverSession = result.chat_session as ApiRecord | undefined;
      if (serverSession) {
        const next = chatSessionFromApi(serverSession);
        setSessions((current) => [next, ...current.filter((session) => session.id !== next.id)]);
        setActiveSessionId(next.id);
        return;
      }
      const task = (result.task as ApiRecord | undefined) ?? {};
      const approval = (result.approval as ApiRecord | undefined) ?? {};
      const approvalRequest = (approval.request as ApiRecord | undefined) ?? {};
      const approvalMetadata = (approvalRequest.metadata as ApiRecord | undefined) ?? {};
      const approvalRisk = (approval.risk as ApiRecord | undefined) ?? {};
      const toolRun = (result.tool_run as ApiRecord | undefined) ?? {};
      const waiting = Boolean(result.approval_required);
      const blocked = Boolean(result.blocked);
      const status: ChatAction["status"] = blocked ? "failed" : waiting ? "waiting_approval" : "completed";
      updateAction(sessionId, message.id, {
        status,
        taskId: text(task.task_id),
        approvalId: text(approval.approval_id),
        riskLevel: text(approvalRisk.level ?? toolRun.risk_level),
        approvalInput: (approvalMetadata.tool_input as ApiRecord | undefined) ?? {},
      });
      const resultMessage: ChatMessage = {
        id: createId("message"),
        role: "assistant",
        content: blocked
          ? `行动未完成：${text(result.output, "工作流被安全策略阻止。")}`
          : waiting
            ? `任务已创建，正在等待审批。任务编号：${shortId(task.task_id)}`
            : `行动已完成。\n${chatActionResult(result)}`,
        createdAt: new Date().toISOString(),
        failed: blocked,
      };
      setSessions((current) => current.map((session) => session.id === sessionId ? {
        ...session,
        messages: [...session.messages, resultMessage],
        updatedAt: resultMessage.createdAt,
      } : session));
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "行动执行失败";
      updateAction(sessionId, message.id, { status: "failed" });
      fail(errorMessage);
    } finally {
      executingActionIds.current.delete(action.proposalId);
    }
  };

  const decideAction = async (message: ChatMessage, decision: "approved" | "rejected") => {
    if (!activeSession || !message.action || message.action.status !== "waiting_approval") return;
    const sessionId = activeSession.id;
    const action = message.action;
    const taskId = action.taskId;
    if (!taskId) return;
    const operationId = action.approvalId || action.proposalId;
    if (executingActionIds.current.has(operationId)) return;
    executingActionIds.current.add(operationId);
    updateAction(sessionId, message.id, { status: "deciding" });
    try {
      const result = await decideChatAction(taskId, decision);
      const serverSession = result.chat_session as ApiRecord | undefined;
      if (serverSession) {
        const next = chatSessionFromApi(serverSession);
        setSessions((current) => [next, ...current.filter((session) => session.id !== next.id)]);
        setActiveSessionId(next.id);
        return;
      }
      const task = (result.task as ApiRecord | undefined) ?? {};
      const resumedToolRun = (result.tool_run as ApiRecord | undefined) ?? {};
      const rejected = decision === "rejected" || text(result.outcome) === "rejected" || text(task.status) === "cancelled";
      const blocked = Boolean(result.blocked);
      const failed = text(result.outcome) === "failed" || text(task.status) === "failed" || text(resumedToolRun.status) === "failed";
      updateAction(sessionId, message.id, { status: rejected ? "cancelled" : blocked || failed ? "failed" : "completed" });
      const resultMessage: ChatMessage = {
        id: createId("message"),
        role: "assistant",
        content: rejected
          ? "Human Root 已拒绝，本次行动没有执行。"
          : blocked
            ? `审批后仍被安全策略阻止：${text(result.output, "行动未执行。")}`
            : failed
              ? `行动执行失败：${text(result.output, text(resumedToolRun.error, "命令没有成功完成。"))}`
              : `审批通过，行动已完成。\n${chatActionResult(result)}`,
        createdAt: new Date().toISOString(),
        failed: blocked || failed,
      };
      setSessions((current) => current.map((session) => session.id === sessionId ? {
        ...session,
        messages: [...session.messages, resultMessage],
        updatedAt: resultMessage.createdAt,
      } : session));
    } catch (error) {
      updateAction(sessionId, message.id, { status: "waiting_approval" });
      fail(error instanceof Error ? error.message : "审批续跑失败");
    } finally {
      executingActionIds.current.delete(operationId);
    }
  };

  const cancelAction = async (message: ChatMessage) => {
    if (!activeSession || !message.action || message.action.status !== "pending") return;
    const sessionId = activeSession.id;
    updateAction(sessionId, message.id, { status: "cancelled" });
    try {
      const result = await cancelChatAction(message.action.proposalId);
      const serverSession = result.session as ApiRecord | undefined;
      if (serverSession) {
        const next = chatSessionFromApi(serverSession);
        setSessions((current) => [next, ...current.filter((session) => session.id !== next.id)]);
      } else {
        await loadServerSessions(sessionId);
      }
    } catch (error) {
      updateAction(sessionId, message.id, { status: "pending" });
      fail(error instanceof Error ? error.message : "取消行动失败");
    }
  };

  if (!chatReady) return <LoadingState />;
  if (!activeSession) return <EmptyState message="服务端对话暂不可用，请检查 API 连接后重试。" />;

  return (
    <section className="chat-layout" aria-label="AI 对话工作区">
      <aside className="chat-sidebar">
        <button className="button chat-new-button" onClick={() => void startNewChat()}><Plus />新对话</button>
        <div className="chat-session-list" aria-label="对话列表">
          {sessions.map((session) => (
            <div className={`chat-session ${session.id === activeSession.id ? "active" : ""}`} key={session.id}>
              <button className="chat-session-open" onClick={() => setActiveSessionId(session.id)}>
                <strong>{session.title || "新对话"}</strong>
                <span>{session.messages.length ? `${session.messages.length} 条消息` : "尚未开始"}</span>
              </button>
              <button className="icon-button" onClick={() => void deleteChat(session.id)} aria-label={`删除对话 ${session.title}`} title="删除对话"><Trash2 /></button>
            </div>
          ))}
        </div>
      </aside>

      <div className="chat-main">
        <div className="chat-toolbar">
          <div>
            <strong>{activeSession.title}</strong>
            <span>对话、模型用量和行动状态已由服务端持久保存</span>
          </div>
          <div className="chat-model-controls">
            <label><span>模式</span><select aria-label="对话模式" value={chatMode} onChange={(event) => setChatMode(event.target.value as "auto" | "chat" | "action" | "agent")}><option value="auto">自动判断</option><option value="chat">只聊天</option><option value="action">计划行动</option><option value="agent">连续 Agent</option></select></label>
            <label><span>服务商</span><select aria-label="对话模型服务商" value={provider} onChange={(event) => setProvider(event.target.value)}>{providerNames.map((name) => <option key={name} value={name}>{formatValue(name)}</option>)}</select></label>
            <label><span>模型</span><select aria-label="对话模型" value={model} onChange={(event) => setModel(event.target.value)}>{availableModels.map((name) => <option key={name} value={name}>{name}</option>)}</select></label>
          </div>
        </div>

        <div className="chat-messages" aria-live="polite">
          {activeSession.messages.length === 0 && <div className="chat-empty"><MessageSquare /><strong>开始一段新对话</strong><span>可以提问、讨论方案，也可以让 AI 帮你整理和创作。</span></div>}
          {activeSession.messages.map((message) => (
            <article className={`chat-message ${message.role} ${message.failed ? "failed" : ""}`} key={message.id}>
              <div className="chat-message-label">{message.role === "user" ? "你" : "AI Company OS"}</div>
              <p>{message.content}</p>
              {message.role === "assistant" && message.provider && <div className="chat-message-meta">
                <span>{formatValue(message.provider)}</span><span>{message.model}</span><span>{message.totalTokens ?? 0} Token</span><span>${(message.cost ?? 0).toFixed(9)}</span>{message.fallbackUsed && <span>已降级</span>}
              </div>}
              {message.action && <div className={`chat-action-card ${message.action.status}`}>
                <div className="chat-action-heading"><Workflow /><div><strong>{message.action.workflowName}</strong><span>{message.action.purpose}</span></div><StatusPill value={message.action.status} /></div>
                <div className="chat-action-detail"><span>执行后将创建受控任务</span><code>{message.action.workflowId}</code></div>
                {message.action.runId && <AgentRunTrace run={activeSession.agentRuns.find((run) => run.id === message.action?.runId)} />}
                {message.action.status === "pending" && <div className="chat-action-buttons"><button className="small-button" onClick={() => void cancelAction(message)}>取消</button><button className="button" onClick={() => void executeAction(message)}><Play />确认执行</button></div>}
                {message.action.status === "waiting_approval" && <div className="chat-approval-block">
                  <div className="chat-approval-facts"><span>风险：{formatValue(message.action.riskLevel, "待评估")}</span><span>审批：{shortId(message.action.approvalId)}</span></div>
                  <code>{chatApprovalPreview(message.action)}</code>
                  <div className="chat-action-buttons"><button className="small-button" onClick={() => void decideAction(message, "rejected")}><X />拒绝</button><button className="button" onClick={() => void decideAction(message, "approved")}><Check />批准并继续</button></div>
                </div>}
                {message.action.taskId && <div className="muted-line">任务：{shortId(message.action.taskId)}</div>}
              </div>}
            </article>
          ))}
          {sendingChatId === activeSession.id && <article className="chat-message assistant pending"><div className="chat-message-label">AI Company OS</div><p>正在思考...</p></article>}
          <div ref={chatEndRef} aria-hidden="true" />
        </div>

        <form className="chat-composer" onSubmit={sendMessage}>
          <textarea
            aria-label="聊天消息"
            placeholder="输入消息，Enter 发送，Shift+Enter 换行"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
          />
          <button className="button chat-send-button" type="submit" aria-label="发送消息" disabled={!draft.trim() || Boolean(sendingChatId) || !model}><Send />发送</button>
        </form>
      </div>
    </section>
  );
}

function AgentRunTrace({ run }: { run?: AgentRun }) {
  if (!run) return null;
  return (
    <div className="agent-run-trace">
      <div className="agent-run-summary"><strong>Agent Run</strong><span>{run.steps.length} / 8 步</span><StatusPill value={run.status} /></div>
      {run.steps.map((step) => (
        <div className="agent-run-step" key={step.id}>
          <span>{step.sequence}</span>
          <strong>{formatValue(step.intent)}</strong>
          <small>{step.taskId ? shortId(step.taskId) : "--"}</small>
          <StatusPill value={step.status} />
        </div>
      ))}
      {run.error && <div className="muted-line">{run.error}</div>}
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
  const providerNames = (data.providers.providers as string[] | undefined) ?? ["local"];
  const allowedModels = (data.providers.allowed_models as Record<string, string[]> | undefined) ?? {};
  const [modelProvider, setModelProvider] = useState(() => text(data.providers.default_provider, "local"));
  const availableModels = allowedModels[modelProvider] ?? [];
  const [modelName, setModelName] = useState(() => text(data.providers.default_model, "deterministic_mock_v1"));
  const [modelPrompt, setModelPrompt] = useState("请总结当前任务并给出三条可执行建议。");
  const [modelSubmitting, setModelSubmitting] = useState(false);
  const [modelResult, setModelResult] = useState<ApiRecord | null>(null);

  useEffect(() => {
    if (!providerNames.includes(modelProvider)) {
      setModelProvider(text(data.providers.default_provider, providerNames[0] ?? "local"));
    }
  }, [data.providers.default_provider, modelProvider, providerNames]);

  useEffect(() => {
    const models = allowedModels[modelProvider] ?? [];
    if (models.length && !models.includes(modelName)) {
      setModelName(models[0]);
    }
  }, [allowedModels, modelName, modelProvider]);
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
  const generateModelOutput = async (event: FormEvent) => {
    event.preventDefault();
    setModelSubmitting(true);
    try {
      const result = await mutate<ApiRecord>("/models/generate", {
        prompt: modelPrompt,
        actor_id: "document_agent_v1",
        purpose: "console_generation",
        provider: modelProvider,
        model_name: modelName,
      });
      setModelResult(result);
      notify(result.blocked ? "模型调用被预算策略阻止。" : "模型调用已完成。");
    } catch (error) {
      fail(error instanceof Error ? error.message : "模型调用失败");
    } finally {
      setModelSubmitting(false);
    }
  };
  const routing = (modelResult?.routing as ApiRecord | undefined) ?? {};
  const usage = (modelResult?.usage as ApiRecord | undefined) ?? {};
  const costLog = (modelResult?.cost_log as ApiRecord | undefined) ?? {};
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
      <section className="two-column work-layout">
        <Panel title="调用 AI 模型" meta="多供应商受控路由">
          <form className="form-grid" onSubmit={generateModelOutput}>
            <Field label="模型服务商"><select value={modelProvider} onChange={(e) => setModelProvider(e.target.value)}>{providerNames.map((name) => <option key={name} value={name}>{formatValue(name)}</option>)}</select></Field>
            <Field label="模型"><select value={modelName} onChange={(e) => setModelName(e.target.value)}>{availableModels.map((name) => <option key={name} value={name}>{name}</option>)}</select></Field>
            <Field label="提示词"><textarea value={modelPrompt} onChange={(e) => setModelPrompt(e.target.value)} required /></Field>
            <button className="button" disabled={modelSubmitting || !modelName}><Bot />{modelSubmitting ? "调用中..." : "调用模型"}</button>
          </form>
        </Panel>
        <Panel title="模型结果" meta={modelResult ? (modelResult.blocked ? "已阻止" : "已完成") : "等待调用"}>
          {modelResult ? <div className="model-result"><p>{text(modelResult.output, "没有生成输出")}</p><div className="system-facts"><Fact label="请求供应商" value={formatValue(routing.requested_provider)} /><Fact label="实际供应商" value={formatValue(routing.actual_provider)} /><Fact label="降级发生" value={routing.fallback_used ? "是" : "否"} /><Fact label="尝试顺序" value={Array.isArray(routing.attempted_providers) ? routing.attempted_providers.map((item) => formatValue(item)).join(" → ") : "--"} /><Fact label="模型" value={text(usage.model_name)} /><Fact label="总 Token" value={text(usage.total_tokens, "0")} /><Fact label="估算费用" value={`$${text(costLog.amount, "0")}`} /></div></div> : <EmptyState message="选择供应商和模型后即可发起受控调用。" />}
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
  const providerNames = (data.providers.providers as string[] | undefined) ?? [];
  const fallbackOrder = (data.providers.fallback_order as string[] | undefined) ?? [];
  const providerDetails = (data.providers.provider_details as Record<string, ApiRecord> | undefined) ?? {};
  const providerRows = providerNames.map((name) => ({ id: name, name, is_default: name === text(data.providers.default_provider), ...(providerDetails[name] ?? {}) }));
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
          <Fact label="已配置供应商" value={providerNames.length ? providerNames.map((name) => formatValue(name)).join("、") : "无"} />
          <Fact label="降级顺序" value={fallbackOrder.length ? fallbackOrder.map((name) => formatValue(name)).join(" → ") : "未启用"} />
          <Fact label="向量嵌入" value={data.embeddings.enabled ? "已启用" : "已禁用"} />
          <Fact label="嵌入模型" value={text(data.embeddings.default_model, "未配置")} />
          <Fact label="向量维度" value={text(data.embeddings.dimensions)} />
          <Fact label="已索引文档" value={text(data.embeddings.indexed_documents, "0")} />
          <Fact label="失败文档" value={text(data.embeddings.failed_documents, "0")} />
          <Fact label="向量存储" value={data.embeddings.vector_store ? "已连接" : "未连接"} />
        </div>
      </Panel>
      <Panel title="模型路由与价格" meta={`${providerRows.length} 个供应商`}>
        <EntityList items={providerRows} empty="没有已配置的模型供应商。" render={(item) => <ProviderRouteItem item={item} />} />
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

function ProviderRouteItem({ item }: { item: ApiRecord }) {
  const models = (item.allowed_models as string[] | undefined) ?? [];
  const pricing = (item.pricing_usd_per_million as Record<string, ApiRecord> | undefined) ?? {};
  const priceText = Object.entries(pricing).map(([model, rates]) => `${model}：输入 $${text(rates.input)} / 输出 $${text(rates.output)}`).join("；");
  return <div className="incident-detail"><EntityRow title={formatValue(item.name)} detail={`默认：${text(item.default_model)} / 可用：${models.join("、") || "无"}`} status={item.is_default ? "默认" : "可用"} /><span className="muted-line">{priceText ? `${priceText}（每百万 Token）` : "价格使用预算策略中的默认单价。"}</span></div>;
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
function statusTone(value: string) { const v = value.toLowerCase(); if (["ok", "ready", "completed", "approved", "enabled", "active", "verified", "executed"].includes(v)) return "good"; if (["failed", "blocked", "rejected", "critical", "not_ready", "forbidden", "cancelled", "open"].includes(v)) return "bad"; if (["pending", "executing", "deciding", "warning", "waiting_approval", "medium", "paused", "need_more_info"].includes(v)) return "warn"; return "neutral"; }
