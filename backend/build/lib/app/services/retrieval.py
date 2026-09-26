from __future__ import annotations

from dataclasses import dataclass

from app.domain.models import Property, PropertyQuery
from app.integrations.rag.pinecone import RAGProviderError, RetrievedChunk


@dataclass(frozen=True)
class SourceChunk:
    source_id: str
    property_id: str
    text: str
    version: str


class GroundedRetriever:
    """Local deterministic retrieval mirror. Pinecone adapter belongs behind this contract."""

    def __init__(self, knowledge_store: object | None = None) -> None:
        self.knowledge_store = knowledge_store

    def for_properties(self, properties: list[Property]) -> list[SourceChunk]:
        return [
            SourceChunk(
                source_id=f"{item.id}:{item.source_version}",
                property_id=item.id,
                version=item.source_version,
                text=(
                    f"Property ID {item.id}. {item.title}. {item.area}, {item.city}. Price PKR {item.price_pkr}. "
                    f"Size {item.size_sqft} sqft, bedrooms {item.bedrooms}. Developer {item.developer}. "
                    f"Schools: {', '.join(item.nearby_schools)}. Hospitals: {', '.join(item.nearby_hospitals)}. "
                    f"{item.payment_plan}. Amenities: {', '.join(item.amenities)}. "
                    f"Investment goals: {', '.join(item.investment_goals) or 'not specified'}."
                ),
            )
            for item in properties
        ]

    def context_for(
        self, query: str, properties: list[Property], top_k: int = 5
    ) -> list[RetrievedChunk]:
        """Query external knowledge only after SQL has fixed property filters."""

        if self.knowledge_store is None or not properties:
            return []
        property_ids = [item.id for item in properties]
        try:
            chunks = self.knowledge_store.query(
                query,
                metadata_filter={"property_id": {"$in": property_ids}},
                top_k=top_k,
            )
        except RAGProviderError:
            return []
        # Treat the remote store as a boundary: never trust its filter enforcement.
        return [chunk for chunk in chunks if chunk.metadata.get("property_id") in property_ids][:top_k]


def recommendation_score(property_item: Property, query: PropertyQuery) -> float:
    """Rank already-filtered inventory without changing availability truth.

    SQL remains authoritative for eligibility. This score only orders eligible rows by
    caller-fit signals and is intentionally deterministic for auditability.
    """
    score = 0.0
    if query.area and query.area.casefold() in property_item.area.casefold():
        score += 4.0
    if query.city and query.city.casefold() == property_item.city.casefold():
        score += 2.0
    if query.max_budget_pkr:
        remaining = max(query.max_budget_pkr - property_item.price_pkr, 0)
        score += 1.0 - (remaining / query.max_budget_pkr)
    if query.bedrooms is not None and property_item.bedrooms >= query.bedrooms:
        score += 1.5
    if query.amenities:
        available = {amenity.casefold() for amenity in property_item.amenities}
        score += 1.0 * len({item.casefold() for item in query.amenities} & available)
    if query.investment_goal and any(
        query.investment_goal.casefold() in value.casefold()
        for value in property_item.investment_goals
    ):
        score += 2.0
    if query.target_size_sqft and property_item.size_sqft:
        diff_ratio = abs(property_item.size_sqft - query.target_size_sqft) / max(query.target_size_sqft, 1)
        if diff_ratio < 0.35:
            score += 3.0 * (1.0 - diff_ratio)
    return score


def rank_properties(properties: list[Property], query: PropertyQuery) -> list[Property]:
    """Stable highest-fit-first ordering for available SQL results."""
    return [
        item
        for _, item in sorted(
            enumerate(properties),
            key=lambda pair: (-recommendation_score(pair[1], query), pair[0]),
        )
    ]
