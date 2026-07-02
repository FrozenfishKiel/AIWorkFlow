export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.trim() || "http://localhost:8000";
export const API_ACCESS_TOKEN = import.meta.env.VITE_API_ACCESS_TOKEN?.trim() || "";
const AUTH_SESSION_STORAGE_KEY = "ai-content-ops.auth-session";

interface StoredAuthSessionRecord {
  access_token: string;
  token_type: string;
  username?: string;
  auth_mode?: string;
  expires_at?: string;
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function getStorage() {
  return typeof localStorage === "undefined" ? null : localStorage;
}

function readStoredAuthSessionRecord(): StoredAuthSessionRecord | null {
  const storage = getStorage();
  const rawValue = storage?.getItem(AUTH_SESSION_STORAGE_KEY);
  if (!rawValue) {
    return null;
  }

  try {
    return JSON.parse(rawValue) as StoredAuthSessionRecord;
  } catch {
    storage?.removeItem(AUTH_SESSION_STORAGE_KEY);
    return null;
  }
}

function writeStoredAuthSessionRecord(session: StoredAuthSessionRecord): void {
  getStorage()?.setItem(AUTH_SESSION_STORAGE_KEY, JSON.stringify(session));
}

export function clearStoredAuthSession(): void {
  getStorage()?.removeItem(AUTH_SESSION_STORAGE_KEY);
}

export function setStoredAccessToken(accessToken: string): void {
  writeStoredAuthSessionRecord({
    access_token: accessToken,
    token_type: "bearer",
  });
}

export function readStoredAccessToken(): string {
  return readStoredAuthSessionRecord()?.access_token?.trim() || "";
}

export function readStoredAuthSession() {
  return readStoredAuthSessionRecord();
}

export function persistAuthSession(session: StoredAuthSessionRecord): void {
  writeStoredAuthSessionRecord(session);
}

function getActiveAccessToken(): string {
  return API_ACCESS_TOKEN || readStoredAccessToken();
}

function normalizeApiErrorDetail(detail: unknown): string | null {
  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail) && detail.length > 0) {
    const firstItem = detail[0];
    if (typeof firstItem === "string") {
      return firstItem;
    }

    if (firstItem && typeof firstItem === "object" && "msg" in firstItem) {
      const message = (firstItem as { msg?: unknown }).msg;
      if (typeof message === "string" && message.trim()) {
        return message;
      }
    }

    return JSON.stringify(firstItem);
  }

  if (detail && typeof detail === "object") {
    return JSON.stringify(detail);
  }

  return null;
}

async function buildApiError(response: Response): Promise<ApiError> {
  let message = `请求失败，状态码 ${response.status}`;
  const contentType = response.headers.get("content-type") || "";

  if (contentType.includes("application/json")) {
    try {
      const payload = (await response.json()) as { detail?: unknown };
      const normalizedDetail = normalizeApiErrorDetail(payload.detail);
      if (normalizedDetail) {
        message = normalizedDetail;
      }
    } catch {
      // Keep the fallback message when the error payload cannot be parsed.
    }
  }

  return new ApiError(message, response.status);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      Accept: "application/json",
      ...(getActiveAccessToken() ? { Authorization: `Bearer ${getActiveAccessToken()}` } : {}),
      // FormData must keep the browser-generated multipart boundary; forcing a
      // JSON content type here would break the future upload path.
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    throw await buildApiError(response);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

async function requestBlob(path: string, init?: RequestInit): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      ...(getActiveAccessToken() ? { Authorization: `Bearer ${getActiveAccessToken()}` } : {}),
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    throw await buildApiError(response);
  }

  return await response.blob();
}

export const apiClient = {
  get: <T>(path: string) => request<T>(path),
  getBlob: (path: string) => requestBlob(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "POST",
      body: body instanceof FormData ? body : body === undefined ? undefined : JSON.stringify(body),
    }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "PUT",
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
};
