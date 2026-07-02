export type AuthMode = "disabled" | "legacy_token" | "password_login";

export interface AuthConfig {
  auth_mode: AuthMode;
  login_enabled: boolean;
  token_ttl_minutes: number;
}

export interface AuthLoginInput {
  username: string;
  password: string;
}

export interface AuthSession {
  access_token: string;
  token_type: string;
  username: string;
  auth_mode: AuthMode;
  expires_at: string;
}

export interface AuthUser {
  username: string;
  auth_mode: AuthMode;
  expires_at: string | null;
}
