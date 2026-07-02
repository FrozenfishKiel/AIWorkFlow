from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AuthConfigRead(BaseModel):
    auth_mode: str = Field(description="Current runtime auth mode for the API.")
    login_enabled: bool = Field(description="Whether the password login endpoint is available.")
    token_ttl_minutes: int = Field(description="Lifetime of issued password-login tokens.")


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, description="Operator username for the minimal Phase 1 login flow.")
    password: str = Field(min_length=1, description="Operator password for the minimal Phase 1 login flow.")


class AuthSessionRead(BaseModel):
    access_token: str = Field(description="Signed bearer token that authorizes protected API requests.")
    token_type: str = Field(description="Bearer token type string returned to the frontend.")
    username: str = Field(description="Authenticated operator username.")
    auth_mode: str = Field(description="Auth mode that issued the current session token.")
    expires_at: datetime = Field(description="UTC timestamp when the issued access token expires.")


class AuthUserRead(BaseModel):
    username: str = Field(description="Authenticated operator username.")
    auth_mode: str = Field(description="How this operator was authenticated for the current request.")
    expires_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when the current session expires, when applicable.",
    )
