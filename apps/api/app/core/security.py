from __future__ import annotations

from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.settings import get_settings

bearer_scheme = HTTPBearer(auto_error=False)


def require_access_token(
    credentials: HTTPAuthorizationCredentials | None,
) -> None:
    """Enforce the optional Phase 1 bearer-token access gate.

    When no token is configured the local developer experience stays unchanged.
    Once a token is configured, every protected route must receive the matching
    bearer token before request handling continues.
    """

    configured_token = get_settings().api_access_token
    if not configured_token:
        return

    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
        or credentials.credentials != configured_token
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
