"""Approved availability keyed by immutable provider identity in Pakistan time."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core.config import settings
from app.repositories.records import (
    AgentScheduleRecord,
    MembershipRecord,
    OrganizationRecord,
    PropertyRecord,
)


def eligible_schedule(
    session, property_id: str, starts_at: datetime, *, agent_subject: str | None = None
) -> bool:
    if not settings.marketplace_enabled:
        return True
    prop = session.get(PropertyRecord, property_id)
    subject = agent_subject or (prop.assigned_staff_id if prop else None)
    if not prop or not subject:
        return False
    org = session.get(OrganizationRecord, prop.organization_id)
    member = session.scalar(
        select(MembershipRecord).where(
            MembershipRecord.organization_id == prop.organization_id,
            MembershipRecord.subject == subject,
            MembershipRecord.active.is_(True),
        )
    )
    if not org or org.status != "approved" or not member:
        return False
    local = (
        starts_at.astimezone(ZoneInfo("Asia/Karachi"))
        if starts_at.tzinfo
        else starts_at.replace(tzinfo=ZoneInfo("Asia/Karachi"))
    )
    if (
        local.astimezone(UTC) <= datetime.now(UTC)
        or local.second
        or local.microsecond
        or local.minute % 30
    ):
        return False
    rows = session.scalars(
        select(AgentScheduleRecord).where(
            AgentScheduleRecord.organization_id == org.id,
            AgentScheduleRecord.subject == member.subject,
            AgentScheduleRecord.approved.is_(True),
        )
    ).all()
    exceptions = [r for r in rows if r.exception_date == local.date().isoformat()]
    if any(r.unavailable for r in exceptions):
        return False
    applicable = (
        exceptions
        if exceptions
        else [r for r in rows if r.exception_date is None and r.weekday == local.weekday()]
    )
    minute = local.hour * 60 + local.minute
    return any(
        not r.unavailable and r.start_minute <= minute and minute + 30 <= r.end_minute
        for r in applicable
    )
