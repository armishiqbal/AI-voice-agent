from __future__ import annotations

# FastAPI resolves the bearer dependency from this endpoint signature.
# ruff: noqa: B008
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlsplit

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient, PyJWKClientConnectionError, PyJWKClientError
from jwt.exceptions import PyJWTError
from sqlalchemy import select

from app.core.config import settings
from app.repositories.database import SessionLocal
from app.repositories.records import StaffUserRecord

_bearer = HTTPBearer(auto_error=False)
_STAFF_ROLES = {"administrator", "manager", "agent"}


@dataclass(frozen=True)
class StaffPrincipal:
    subject: str
    email: str
    display_name: str
    role: str


@lru_cache(maxsize=2)
def _jwks_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url, cache_keys=True, timeout=4)


def _supabase_issuer_and_jwks_url() -> tuple[str, str]:
    configured_url = (settings.supabase_url or "").rstrip("/")
    if not configured_url:
        raise HTTPException(status_code=503, detail="Staff identity provider is not configured")
    parsed = urlsplit(configured_url)
    local_development = settings.app_env == "development" and parsed.hostname in {
        "localhost",
        "127.0.0.1",
        "::1",
    }
    if (
        not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or (parsed.scheme != "https" and not (local_development and parsed.scheme == "http"))
        or parsed.path not in ("", "/")
    ):
        raise HTTPException(status_code=503, detail="Staff identity provider configuration is invalid")
    issuer = f"{configured_url}/auth/v1"
    return issuer, f"{issuer}/.well-known/jwks.json"


def require_staff(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> StaffPrincipal:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A verified staff session is required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    issuer, jwks_url = _supabase_issuer_and_jwks_url()
    token = credentials.credentials
    try:
        signing_key = _jwks_client(jwks_url).get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
            issuer=issuer,
            options={"require": ["exp", "sub", "iss", "aud"]},
            leeway=30,
        )
    except PyJWKClientConnectionError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Staff identity provider is temporarily unavailable",
        ) from error
    except (PyJWKClientError, PyJWTError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Staff access token is invalid or expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error

    subject = claims.get("sub")
    email = claims.get("email")
    if (
        not isinstance(subject, str)
        or not subject
        or len(subject) > 128
        or not isinstance(email, str)
        or not email
        or claims.get("email_verified") is not True
    ):
        raise HTTPException(status_code=401, detail="A verified staff identity is required")
    if claims.get("aal") != "aal2":
        raise HTTPException(status_code=403, detail="Staff authenticator MFA is required")

    with SessionLocal() as session:
        staff = session.scalar(
            select(StaffUserRecord).where(
                StaffUserRecord.provider_subject == subject,
                StaffUserRecord.is_active.is_(True),
            )
        )
        if staff is None or staff.role not in _STAFF_ROLES:
            raise HTTPException(status_code=403, detail="Staff account is not authorized")
        return StaffPrincipal(
            subject=staff.provider_subject,
            email=staff.email,
            display_name=staff.display_name,
            role=staff.role,
        )


def require_roles(*roles: str):
    allowed_roles = frozenset(roles)

    def role_dependency(staff: StaffPrincipal = Depends(require_staff)) -> StaffPrincipal:
        if staff.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Staff role cannot perform this action")
        return staff

    return role_dependency
