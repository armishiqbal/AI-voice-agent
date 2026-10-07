"""Verified provider identities exchanged for revocable, CSRF protected sessions."""

# FastAPI resolves validated dependencies from endpoint signatures.
# ruff: noqa: B008
import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.catalog.staff_auth import _jwks_client, _supabase_issuer_and_jwks_url
from app.core.config import settings
from app.repositories.database import SessionLocal
from app.repositories.records import (
    ApplicationSessionRecord,
    CustomerProfileRecord,
    MembershipRecord,
    StaffUserRecord,
)

router = APIRouter(prefix="/v1/auth", tags=["sessions"])
COOKIE = "awaaz_session"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


@dataclass(frozen=True)
class Identity:
    subject: str
    email: str
    assurance: str


class Exchange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    access_token: str = Field(min_length=20, max_length=16384)


def require_identity(request: Request) -> Identity:
    token = request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(401, "Sign in with a verified email")
    with SessionLocal() as session:
        record = session.get(ApplicationSessionRecord, digest(token))
        now = datetime.now(UTC)
        if record is None or record.revoked or record.expires_at.replace(tzinfo=UTC) <= now:
            raise HTTPException(401, "Session expired or revoked")
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            csrf = request.headers.get("x-csrf-token", "")
            if not secrets.compare_digest(record.csrf_hash, digest(csrf)):
                raise HTTPException(403, "CSRF token is required")
        return Identity(record.subject, record.email, record.assurance)


@router.post("/session")
def exchange(payload: Exchange, request: Request, response: Response):
    # JSON exchanges must originate from the website origin, not a third party form.
    origin = request.headers.get("origin")
    forwarded = (
        request.headers.get("x-forwarded-host") if settings.app_env == "development" else None
    )
    if origin and origin.split("://", 1)[-1] != (forwarded or request.headers.get("host")):
        raise HTTPException(403, "Session origin is not allowed")
    issuer, url = _supabase_issuer_and_jwks_url()
    try:
        key = _jwks_client(url).get_signing_key_from_jwt(payload.access_token).key
        claims = jwt.decode(
            payload.access_token,
            key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
            issuer=issuer,
            options={"require": ["exp", "sub", "iss", "aud"]},
        )
    except jwt.PyJWTError as error:
        raise HTTPException(401, "Provider session is invalid") from error
    except Exception as error:
        raise HTTPException(503, "Identity provider is unavailable") from error
    subject, email = claims.get("sub"), claims.get("email")
    if not isinstance(subject, str) or len(subject) > 128 or not isinstance(email, str):
        raise HTTPException(401, "Verify your email first")
    import httpx

    try:
        verified = httpx.get(
            f"{issuer}/user",
            headers={
                "Authorization": f"Bearer {payload.access_token}",
                "apikey": settings.supabase_anon_key or "",
            },
            timeout=5,
        )
        user = verified.json()
        if (
            verified.status_code != 200
            or user.get("id") != subject
            or user.get("email") != email
            or not user.get("email_confirmed_at")
        ):
            raise HTTPException(401, "Verify your email first")
    except httpx.HTTPError as error:
        raise HTTPException(503, "Identity verification is unavailable") from error
    assurance = claims.get("aal", "aal1")
    with SessionLocal.begin() as session:
        staff = session.get(StaffUserRecord, subject)
        member = session.scalar(
            select(MembershipRecord).where(
                MembershipRecord.subject == subject, MembershipRecord.active.is_(True)
            )
        )
        if (staff and staff.is_active or member) and assurance != "aal2":
            raise HTTPException(403, "Authenticator MFA is required for workspace access")
        token, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
        expiry = min(
            datetime.fromtimestamp(claims["exp"], UTC), datetime.now(UTC) + timedelta(hours=8)
        )
        if settings.customer_features_enabled:
            from app.core.pii import ContactCipher

            profile = session.get(CustomerProfileRecord, subject)
            if not profile:
                profile = CustomerProfileRecord(
                    subject=subject,
                    email_ciphertext=ContactCipher().encrypt(email),
                    verified_at=datetime.now(UTC),
                )
                session.add(profile)
            else:
                profile.email_ciphertext = ContactCipher().encrypt(email)
                profile.verified_at = datetime.now(UTC)
        session.add(
            ApplicationSessionRecord(
                token_hash=digest(token),
                subject=subject,
                email=email,
                assurance=assurance,
                csrf_hash=digest(csrf),
                expires_at=expiry,
                revoked=False,
            )
        )
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        secure=settings.app_env != "development",
        samesite="lax",
        max_age=max(0, int((expiry - datetime.now(UTC)).total_seconds())),
        path="/",
    )
    return {"subject": subject, "email": email, "csrf_token": csrf, "expires_at": expiry}


@router.get("/session")
def session_info(identity: Identity = Depends(require_identity)):
    with SessionLocal() as session:
        staff = session.get(StaffUserRecord, identity.subject)
        memberships = session.scalars(
            select(MembershipRecord).where(
                MembershipRecord.subject == identity.subject, MembershipRecord.active.is_(True)
            )
        ).all()
        return {
            "subject": identity.subject,
            "email": identity.email,
            "assurance": identity.assurance,
            "is_platform_staff": bool(staff and staff.is_active),
            "organizations": [{"id": m.organization_id, "role": m.role} for m in memberships],
        }


@router.post("/logout")
def logout(request: Request, response: Response, identity: Identity = Depends(require_identity)):
    with SessionLocal.begin() as session:
        record = session.get(ApplicationSessionRecord, digest(request.cookies[COOKIE]))
        record.revoked = True
    response.delete_cookie(COOKIE, path="/")
    return {"status": "signed_out"}


@router.get("/csrf")
def csrf_token(request: Request, identity: Identity = Depends(require_identity)):
    token = secrets.token_urlsafe(32)
    with SessionLocal.begin() as session:
        record = session.get(ApplicationSessionRecord, digest(request.cookies[COOKIE]))
        record.csrf_hash = digest(token)
    return {"csrf_token": token}
