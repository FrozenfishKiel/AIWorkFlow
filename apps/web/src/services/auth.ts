import { apiClient, clearStoredAuthSession, persistAuthSession, readStoredAuthSession as readStoredSessionRecord } from "./api";
import type { AuthConfig, AuthLoginInput, AuthSession, AuthUser } from "../types/auth";

export async function fetchAuthConfig(): Promise<AuthConfig> {
  return await apiClient.get<AuthConfig>("/auth/config");
}

export async function loginOperator(payload: AuthLoginInput): Promise<AuthSession> {
  const session = await apiClient.post<AuthSession>("/auth/login", payload);
  persistAuthSession(session);
  return session;
}

export async function fetchCurrentUser(): Promise<AuthUser> {
  return await apiClient.get<AuthUser>("/auth/me");
}

export function readStoredAuthSession(): AuthSession | null {
  const session = readStoredSessionRecord();
  if (!session?.access_token || !session.token_type) {
    return null;
  }
  return session as AuthSession;
}

export function logoutOperator(): void {
  clearStoredAuthSession();
}
