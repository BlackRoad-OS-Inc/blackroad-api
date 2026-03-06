"""JWT authentication middleware (issue #1).

Supports both JWT Bearer tokens and X-BR-KEY API key authentication.
JWT_SECRET environment variable must be set for JWT validation.
Falls back to API key auth when JWT is not configured.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request, status


def _b64decode(data: str) -> bytes:
    """Decode base64url with padding."""
    padding = 4 - len(data) % 4
    return urlsafe_b64decode(data + "=" * padding)


def _b64encode(data: bytes) -> str:
    """Encode base64url without padding."""
    return urlsafe_b64encode(data).rstrip(b"=").decode()


def _jwt_secret() -> str | None:
    return os.getenv("JWT_SECRET")


def create_jwt(payload: dict, secret: str | None = None, expires_in: int = 3600) -> str:
    """Create a simple HS256 JWT token."""
    secret = secret or _jwt_secret()
    if not secret:
        raise ValueError("JWT_SECRET not configured")

    header = _b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload_copy = {**payload, "iat": int(time.time()), "exp": int(time.time()) + expires_in}
    body = _b64encode(json.dumps(payload_copy).encode())
    signing_input = f"{header}.{body}"
    sig = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    signature = _b64encode(sig)
    return f"{header}.{body}.{signature}"


def verify_jwt(token: str, secret: str | None = None) -> dict:
    """Verify an HS256 JWT token and return the payload."""
    secret = secret or _jwt_secret()
    if not secret:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "JWT_SECRET not configured")

    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token format")

    header_b64, payload_b64, sig_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}"
    expected_sig = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    actual_sig = _b64decode(sig_b64)

    if not hmac.compare_digest(expected_sig, actual_sig):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token signature")

    payload = json.loads(_b64decode(payload_b64))
    if payload.get("exp", 0) < time.time():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired")

    return payload


def jwt_or_api_key(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_br_key: Optional[str] = Header(None, alias="X-BR-KEY"),
) -> dict:
    """Authenticate via JWT Bearer token or X-BR-KEY API key.

    Returns a dict with at minimum {"authenticated": True, "method": "jwt"|"api_key"}.
    """
    # Try JWT first
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        secret = _jwt_secret()
        if secret:
            payload = verify_jwt(token, secret)
            return {"authenticated": True, "method": "jwt", **payload}

    # Fall back to API key
    if x_br_key:
        from app.config import get_settings
        settings = get_settings()
        if settings.allowed_api_keys and any(
            hmac.compare_digest(x_br_key, key) for key in settings.allowed_api_keys
        ):
            return {"authenticated": True, "method": "api_key"}

    # In development mode, allow unauthenticated access
    env = os.getenv("NODE_ENV", "development")
    if env == "development":
        return {"authenticated": False, "method": "none", "env": "development"}

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication. Provide Bearer JWT or X-BR-KEY header.",
    )
