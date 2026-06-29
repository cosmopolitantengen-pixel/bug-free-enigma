export type ApiRecord = Record<string, unknown>;

export async function apiRequest<T>(
  apiBase: string,
  path: string,
  init: RequestInit = {},
  authToken = getStoredApiToken(),
): Promise<T> {
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...init.headers,
  };
  if (authToken) {
    Object.assign(headers, { Authorization: `Bearer ${authToken}` });
  }
  let response: Response;
  try {
    response = await fetch(`${apiBase.replace(/\/$/, "")}${path}`, {
      ...init,
      headers,
      signal: init.signal ?? AbortSignal.timeout(10_000),
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "TimeoutError") {
      throw new Error(`请求超时：${path}`);
    }
    throw error;
  }
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = payload && typeof payload === "object" && "detail" in payload
      ? String(payload.detail)
      : `请求失败：${response.status} ${response.statusText}`;
    throw new Error(detail);
  }
  return payload as T;
}

export function getStoredApiToken(): string {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem("ai-company-os-api-token") ?? "";
}

export function storeApiToken(token: string): void {
  if (typeof window === "undefined") return;
  const trimmed = token.trim();
  if (trimmed) {
    window.localStorage.setItem("ai-company-os-api-token", trimmed);
  } else {
    window.localStorage.removeItem("ai-company-os-api-token");
  }
}

export function text(value: unknown, fallback = "--"): string {
  if (value === null || value === undefined || value === "") return fallback;
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export function shortId(value: unknown): string {
  const id = text(value);
  return id.length > 28 ? `${id.slice(0, 12)}...${id.slice(-8)}` : id;
}

export function formatDate(value: unknown): string {
  if (typeof value !== "string") return "--";
  const date = new Date(value);
  return Number.isNaN(date.valueOf())
    ? value
    : date.toLocaleString("zh-CN", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      });
}

const VALUE_LABELS: Record<string, string> = {
  acknowledge: "确认",
  acknowledged: "已确认",
  active: "运行中",
  approve: "批准",
  approved: "已批准",
  block: "阻止",
  blocked: "已阻止",
  cancelled: "已取消",
  capability: "能力管理",
  completed: "已完成",
  compliance: "合规",
  connected: "已连接",
  create_task: "创建任务",
  critical: "严重",
  data: "数据",
  deepseek: "DeepSeek",
  deferred: "已延后",
  deterministic: "确定性本地模型",
  disabled: "已禁用",
  document: "文档",
  enabled: "已启用",
  engineering: "工程",
  executed: "已执行",
  executive: "管理层",
  failed: "失败",
  finance: "财务",
  forbidden: "已禁止",
  high: "高风险",
  human_root: "人类最高管理员",
  internal: "内部",
  knowledge: "知识管理",
  local: "本地",
  low: "低风险",
  medium: "中风险",
  native: "原生",
  need_more_info: "需要更多信息",
  none: "无",
  not_configured: "未配置",
  not_connected: "未连接",
  not_ready: "未就绪",
  no: "否",
  ok: "正常",
  open: "待处理",
  openai: "OpenAI",
  operations: "运营",
  paused: "已暂停",
  pending: "待处理",
  planned: "已规划",
  postgresql: "PostgreSQL",
  product: "产品",
  project: "项目管理",
  quality: "质量",
  ready: "就绪",
  reject: "拒绝",
  rejected: "已拒绝",
  resolve: "解决",
  resolved: "已解决",
  resumed: "已恢复",
  running: "运行中",
  safety: "安全",
  sqlite: "SQLite",
  started: "已开始",
  unknown: "未知",
  verified: "已验证",
  waiting_approval: "等待审批",
  warning: "警告",
  yes: "是",
};

export function formatValue(value: unknown, fallback = "--"): string {
  const raw = text(value, fallback);
  return VALUE_LABELS[raw.toLowerCase()] ?? raw.replaceAll("_", " ");
}
