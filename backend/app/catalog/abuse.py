"""Shared SQL abuse windows: no raw IP or contact details are stored."""

import asyncio
import hashlib
import time

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings
from app.repositories.database import SessionLocal
from app.repositories.records import MarketplaceRateRecord


def allow(address: str, scope: str, limit: int) -> bool:
    window = int(time.time() // 60)
    key = hashlib.sha256(f"{address}:{scope}".encode()).hexdigest()
    with SessionLocal.begin() as session:
        dialect = session.bind.dialect.name
        if dialect == "postgresql":
            insert = pg_insert
        elif dialect == "sqlite":
            insert = sqlite_insert
        else:
            return False
        statement = (
            insert(MarketplaceRateRecord)
            .values(key=key, window=window, hits=1)
            .on_conflict_do_update(
                index_elements=["key", "window"], set_={"hits": MarketplaceRateRecord.hits + 1}
            )
            .returning(MarketplaceRateRecord.hits)
        )
        hits = session.scalar(statement)
        session.execute(
            delete(MarketplaceRateRecord).where(MarketplaceRateRecord.window < window - 5)
        )
        return hits <= limit


class MarketplaceAbuseMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if settings.marketplace_enabled and request.method == "POST":
            limits = {
                "/v1/public/viewings/request-otp": 5,
                "/v1/public/viewings/verify-otp": 15,
                "/v1/public/inquiries": 20,
                "/v1/public/reports": 10,
                "/v1/auth/session": 10,
                "/v1/public/alerts/unsubscribe": 20,
            }
            limit = limits.get(request.url.path)
            if limit:
                try:
                    allowed = await asyncio.to_thread(
                        allow,
                        request.client.host if request.client else "unknown",
                        request.url.path,
                        limit,
                    )
                except SQLAlchemyError:
                    return JSONResponse(
                        {"detail": "Request protection is unavailable"}, status_code=503
                    )
                if not allowed:
                    return JSONResponse(
                        {"detail": "Please wait before trying again"},
                        status_code=429,
                        headers={"Retry-After": "60"},
                    )
        return await call_next(request)
