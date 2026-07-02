from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.settings import get_settings

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedUser:
    username: str
    auth_mode: str
    expires_at: datetime | None = None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _encode_segment(raw_bytes: bytes) -> str:
    return base64.urlsafe_b64encode(raw_bytes).decode("utf-8").rstrip("=")


def _decode_segment(raw_value: str) -> bytes:
    padding = "=" * (-len(raw_value) % 4)
    return base64.urlsafe_b64decode(f"{raw_value}{padding}")


def _build_signature(payload_segment: str, secret_key: str) -> str:
    digest = hmac.new(
        secret_key.encode("utf-8"),
        payload_segment.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return _encode_segment(digest)


def issue_login_token(username: str) -> tuple[str, datetime]:
    """Create a signed operator token for the minimal password-login flow."""

    settings = get_settings()
    issued_at = _utc_now()
    expires_at = issued_at + timedelta(minutes=settings.auth_token_ttl_minutes)
    payload = {
        "sub": username,
        "auth_mode": "password_login",
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
        "iss": settings.auth_token_issuer,
    }
    payload_segment = _encode_segment(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature_segment = _build_signature(payload_segment, settings.auth_secret_key or "")
    return f"{payload_segment}.{signature_segment}", expires_at


def verify_login_credentials(username: str, password: str) -> bool:
    """Check operator credentials without introducing a database dependency."""

    settings = get_settings()
    if settings.auth_mode != "password_login":
        return False
    return hmac.compare_digest(username, settings.auth_login_username or "") and hmac.compare_digest(
        password,
        settings.auth_login_password or "",
    )


def _decode_login_token(token: str) -> AuthenticatedUser:
    settings = get_settings()
    try:
        payload_segment, signature_segment = token.split(".", 1)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid access token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    expected_signature = _build_signature(payload_segment, settings.auth_secret_key or "")
    if not hmac.compare_digest(signature_segment, expected_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = json.loads(_decode_segment(payload_segment))
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid access token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if payload.get("iss") != settings.auth_token_issuer:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expires_at = datetime.fromtimestamp(int(payload.get("exp", 0)), tz=timezone.utc)
    if expires_at <= _utc_now():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username = str(payload.get("sub") or "").strip()
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AuthenticatedUser(
        username=username,
        auth_mode="password_login",
        expires_at=expires_at,
    )


def require_authenticated_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> AuthenticatedUser:
    """Resolve the current operator from either legacy or login-based auth."""

    settings = get_settings()

    if settings.auth_mode == "disabled":
        user = AuthenticatedUser(username="local-dev", auth_mode="disabled")
        request.state.authenticated_user = user
        return user

    if credentials is None or credentials.scheme.lower() != "bearer":
        detail = (
            "Missing or invalid bearer token."
            if settings.auth_mode == "legacy_token"
            else "Missing or invalid access token."
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )

    if settings.auth_mode == "legacy_token":
        if not hmac.compare_digest(credentials.credentials, settings.api_access_token or ""):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid bearer token.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user = AuthenticatedUser(username="token-operator", auth_mode="legacy_token")
        request.state.authenticated_user = user
        return user

    user = _decode_login_token(credentials.credentials)
    request.state.authenticated_user = user
    return user


def get_request_user(request: Request) -> AuthenticatedUser:
    user = getattr(request.state, "authenticated_user", None)
    if not isinstance(user, AuthenticatedUser):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authenticated user.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
