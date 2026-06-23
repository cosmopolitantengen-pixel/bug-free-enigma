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
      throw new Error(`Request timed out: ${path}`);
    }
    throw error;
  }
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = payload && typeof payload === "object" && "detail" in payload
      ? String(payload.detail)
      : `${response.status} ${response.statusText}`;
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
  return Number.isNaN(date.valueOf()) ? value : date.toLocaleString();
}
