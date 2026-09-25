from __future__ import annotations

from typing import Literal, TypedDict

LeadTemperature = Literal["hot", "warm", "cold"]


class LeadScoreResult(TypedDict):
    score: int
    temperature: LeadTemperature
    factors: list[str]
    recommended_action: str


URGENT_KEYWORDS = (
    "urgent",
    "immediately",
    "ready cash",
    "cash",
    "kal",
    "aaj",
    "this week",
    "token",
    "bayana",
    "deal close",
    "asap",
    "final",
)


def score_lead(
    budget_pkr: int | None = None,
    intent: str | None = None,
    booked_visit: bool = False,
    history: list[str] | None = None,
) -> LeadScoreResult:
    """Calculate lead temperature and qualification score (Hot / Warm / Cold).

    Evaluates commercial intent, verified budget, site tour booking, and buyer timeline.
    """
    score = 0
    factors: list[str] = []

    # 1. Site visit commitment
    if booked_visit:
        score += 40
        factors.append("In-person site visit requested/booked (+40)")

    # 2. Budget band evaluation
    if budget_pkr is not None:
        if budget_pkr >= 20_000_000:
            score += 30
            factors.append(f"High-net-worth budget PKR {budget_pkr:,} (+30)")
        elif budget_pkr >= 10_000_000:
            score += 20
            factors.append(f"Prime residential budget PKR {budget_pkr:,} (+20)")
        else:
            score += 10
            factors.append(f"Affordable segment budget PKR {budget_pkr:,} (+10)")
    else:
        factors.append("Budget not yet disclosed (+0)")

    # 3. Intent qualification
    normalized_intent = (intent or "").lower()
    if normalized_intent == "commercial":
        score += 25
        factors.append("High-yield commercial inquiry (+25)")
    elif normalized_intent in ("buy", "invest"):
        score += 20
        factors.append("Active buyer/investor profile (+20)")
    elif normalized_intent == "rent":
        score += 10
        factors.append("Rental tenant inquiry (+10)")

    # 4. Urgency & Cash buyer signals
    combined_history = " ".join(history or []).lower()
    if any(k in combined_history for k in URGENT_KEYWORDS):
        score += 15
        factors.append("High-urgency purchasing signal detected (+15)")

    # Normalize to max 100
    total_score = min(100, score)

    # Classify temperature
    if total_score >= 65:
        temperature: LeadTemperature = "hot"
        recommended_action = (
            "Priority Routing: Immediate senior consultant WhatsApp outreach & instant property dossier dispatch."
        )
    elif total_score >= 35:
        temperature = "warm"
        recommended_action = (
            "Standard Pipeline: Automated 24-hour follow-up with matching verified inventory recommendations."
        )
    else:
        temperature = "cold"
        recommended_action = (
            "Nurture Campaign: Keep lead updated on quarterly market trends and new installment projects."
        )

    return {
        "score": total_score,
        "temperature": temperature,
        "factors": factors,
        "recommended_action": recommended_action,
    }
