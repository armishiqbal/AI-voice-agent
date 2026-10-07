"""Safe public marketplace directories and bounded viewport discovery."""

# FastAPI resolves validated dependencies from endpoint signatures.
# ruff: noqa: B008
from math import floor

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select

from app.catalog.public import PublicCatalogRepository, get_public_catalog, list_public_listings
from app.core.config import settings
from app.repositories.database import SessionLocal
from app.repositories.listing_visibility import public_listing_conditions
from app.repositories.records import (
    AreaGuideRecord,
    LocationRecord,
    MembershipRecord,
    OrganizationRecord,
    PropertyRecord,
)

router = APIRouter(prefix="/v1/public", tags=["marketplace discovery"])


@router.get("/cities")
def active_cities():
    """Return cities that currently have at least one publicly eligible listing."""
    with SessionLocal() as session:
        cities = session.scalars(
            select(PropertyRecord.city)
            .where(*public_listing_conditions())
            .distinct()
            .order_by(PropertyRecord.city)
        ).all()
    return {"data": cities}


@router.get("/locations")
def locations(
    q: str = Query(default="", max_length=128),
    city: str | None = Query(default=None, max_length=64),
):
    with SessionLocal() as session:
        stmt = select(LocationRecord).where(LocationRecord.reviewed.is_(True))
        if city:
            stmt = stmt.where(LocationRecord.city == city)
        records = session.scalars(stmt.order_by(LocationRecord.city, LocationRecord.area)).all()
        found = [
            r
            for r in records
            if not q
            or any(q.casefold() in value.casefold() for value in [r.city, r.area, *r.aliases])
        ][:30]
        return {
            "data": [
                {
                    "id": r.id,
                    "city": r.city,
                    "city_slug": r.city_slug,
                    "area": r.area,
                    "area_slug": r.area_slug,
                    "label": f"{r.area}, {r.city}" if r.area else r.city,
                }
                for r in found
            ]
        }


@router.get("/areas")
def guides():
    with SessionLocal() as session:
        records = session.scalars(
            select(AreaGuideRecord)
            .where(
                AreaGuideRecord.publication_status == "published",
                AreaGuideRecord.reviewed_at.is_not(None),
            )
            .order_by(AreaGuideRecord.city_slug, AreaGuideRecord.area_slug)
        ).all()
        return {
            "data": [
                {
                    "city_slug": r.city_slug,
                    "area_slug": r.area_slug,
                    "title": r.title,
                    "reviewed_at": r.reviewed_at,
                }
                for r in records
            ]
        }


def agency_public(o):
    return {
        "id": o.id,
        "slug": o.slug,
        "name": o.name,
        "description": o.description,
        "contact_email": o.contact_email,
        "contact_phone": o.contact_phone,
        "coverage": o.coverage,
        "approved_at": o.approved_at,
    }


@router.get("/agencies")
def agencies():
    with SessionLocal() as session:
        return {
            "data": [
                agency_public(o)
                for o in session.scalars(
                    select(OrganizationRecord)
                    .where(OrganizationRecord.status == "approved")
                    .order_by(OrganizationRecord.name)
                ).all()
            ]
        }


@router.get("/agencies/{slug}")
def agency_detail(slug: str):
    with SessionLocal() as session:
        org = session.scalar(
            select(OrganizationRecord).where(
                OrganizationRecord.slug == slug, OrganizationRecord.status == "approved"
            )
        )
        if not org:
            raise HTTPException(404, "Approved agency was not found")
        return agency_public(org)


def agent_public(m, o):
    return {
        "slug": m.slug,
        "name": m.display_name,
        "languages": m.languages,
        "agency": agency_public(o),
    }


@router.get("/agents")
def agents():
    with SessionLocal() as session:
        records = session.execute(
            select(MembershipRecord, OrganizationRecord)
            .join(OrganizationRecord, MembershipRecord.organization_id == OrganizationRecord.id)
            .where(
                OrganizationRecord.status == "approved",
                MembershipRecord.active.is_(True),
                MembershipRecord.profile_approved.is_(True),
                MembershipRecord.slug.is_not(None),
            )
        ).all()
        return {"data": [agent_public(m, o) for m, o in records]}


@router.get("/agents/{slug}")
def agent_detail(slug: str):
    response = agents()
    result = next((r for r in response["data"] if r["slug"] == slug), None)
    if not result:
        raise HTTPException(404, "Approved agent was not found")
    return result


@router.get("/listings/map")
def map_listings(
    request: Request,
    west: float = Query(ge=-180, le=180),
    east: float = Query(ge=-180, le=180),
    south: float = Query(ge=-90, le=90),
    north: float = Query(ge=-90, le=90),
    zoom: int = Query(default=10, ge=0, le=22),
    catalog: PublicCatalogRepository = Depends(get_public_catalog),
):
    if not settings.map_enabled:
        raise HTTPException(503, "Map search is not enabled")
    if west >= east or south >= north:
        raise HTTPException(422, "Invalid viewport")
    # Reuse validated endpoint filter contract; viewport markers are independent of result pagination.
    import inspect

    from pydantic import TypeAdapter

    hints = __import__("typing").get_type_hints(list_public_listings)
    filters = {}
    for key in inspect.signature(list_public_listings).parameters:
        if key in {"catalog", "page", "page_size"}:
            continue
        values = request.query_params.getlist(key)
        if values:
            try:
                filters[key] = TypeAdapter(hints[key]).validate_python(
                    values if key == "amenities" else values[0]
                )
            except ValueError as error:
                raise HTTPException(422, f"Invalid filter: {key}") from error
    try:
        result = catalog.list_public(page=1, page_size=5000, **filters)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    features = []
    groups = {}
    cell = 360 / (2 ** (min(zoom, 18) + 3))
    for p in result.data:
        if not p.coordinates:
            continue
        lon, lat = p.coordinates.longitude, p.coordinates.latitude
        key = (floor(lon / cell), floor(lat / cell))
        groups.setdefault(key, []).append(p)
    for key, items in groups.items():
        lon = sum(p.coordinates.longitude for p in items) / len(items)
        lat = sum(p.coordinates.latitude for p in items) / len(items)
        first = items[0]
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "cluster": len(items) > 1,
                    "count": len(items),
                    "slug": first.slug if len(items) == 1 else None,
                    "title": first.title if len(items) == 1 else f"{len(items)} properties",
                    "price_pkr": first.price_pkr if len(items) == 1 else None,
                    "availability_status": first.availability_status if len(items) == 1 else None,
                },
            }
        )
    unbounded = {k: v for k, v in filters.items() if k not in {"west", "east", "south", "north"}}
    all_count = catalog.list_public(page_size=1, **unbounded).pagination.total
    mapped_count = catalog.list_public(
        page_size=1, **unbounded, west=-180, east=180, south=-90, north=90
    ).pagination.total
    return {
        "type": "FeatureCollection",
        "features": features,
        "matching_viewport": result.pagination.total,
        "matching_total": all_count,
        "unmapped_count": all_count - mapped_count,
        "truncated": result.pagination.total > 5000,
    }


from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Report(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: str = Field(min_length=1, max_length=64)
    category: Literal["unavailable", "incorrect_facts", "photo_permission", "duplicate", "other"]


@router.post("/reports", status_code=201)
def report(payload: Report):
    from uuid import uuid4

    from app.repositories.records import ListingReportRecord

    if not PublicCatalogRepository().get_public_by_id(payload.property_id):
        raise HTTPException(404, "Published property was not found")
    rid = str(uuid4())
    with SessionLocal.begin() as session:
        session.add(
            ListingReportRecord(
                id=rid, property_id=payload.property_id, category=payload.category, status="new"
            )
        )
    return {"reference": rid, "status": "recorded"}
