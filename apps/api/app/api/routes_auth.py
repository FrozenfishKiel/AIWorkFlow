from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials

from app.core.security import (
    bearer_scheme,
    get_request_user,
    issue_login_token,
    require_authenticated_user,
    verify_login_credentials,
)
from app.core.settings import get_settings
from app.schemas.auth import AuthConfigRead, AuthSessionRead, AuthUserRead, LoginRequest

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/config", response_model=AuthConfigRead)
def get_auth_config() -> AuthConfigRead:
    """Expose the minimal auth mode so the web console can choose its entrypoint."""

    settings = get_settings()
    return AuthConfigRead(
        auth_mode=settings.auth_mode,
        login_enabled=settings.auth_mode == "password_login",
        token_ttl_minutes=settings.auth_token_ttl_minutes,
    )


@router.post("/login", response_model=AuthSessionRead)
def login(payload: LoginRequest) -> AuthSessionRead:
    """Issue a short-lived operator session without introducing a user table yet."""

    settings = get_settings()
    if settings.auth_mode != "password_login":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Password login is not enabled.",
        )

    if not verify_login_credentials(payload.username, payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token, expires_at = issue_login_token(payload.username)
    return AuthSessionRead(
        access_token=access_token,
        token_type="bearer",
        username=payload.username,
        auth_mode="password_login",
        expires_at=expires_at,
    )


@router.get("/me", response_model=AuthUserRead)
def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthUserRead:
    """Return the current operator identity when the request is authenticated."""

    require_authenticated_user(request, credentials)
    user = get_request_user(request)
    return AuthUserRead(
        username=user.username,
        auth_mode=user.auth_mode,
        expires_at=user.expires_at,
    )
