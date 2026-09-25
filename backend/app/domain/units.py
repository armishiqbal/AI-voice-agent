from __future__ import annotations

import re
from typing import TypedDict

SQFT_PER_MARLA = 225
SQFT_PER_KANAL = 4500
SQFT_PER_GAZ = 9  # 1 Square Yard / Gaz = 9 sq ft
SQFT_PER_ACRE = 43560  # 8 kanals


class LandSizeResult(TypedDict):
    size_sqft: int
    unit: str
    quantity: float
    formatted: str


COLLOQUIAL_UNITS: list[tuple[str, str, float]] = [
    (r"\b(?:dedh|dehr|daydh)\s*kanal\b", "kanal", 1.5),
    (r"\b(?:dhai|dhaee|dhay)\s*kanal\b", "kanal", 2.5),
    (r"\b(?:aadha|adha)\s*kanal\b", "kanal", 0.5),
    (r"\b(?:sawa)\s*kanal\b", "kanal", 1.25),
    (r"\b(?:paunay?|pone)\s*(?:do)\s*kanal\b", "kanal", 1.75),
    (r"\b(?:dedh|dehr|daydh)\s*(?:marla|marley|marle)\b", "marla", 1.5),
    (r"\b(?:dhai|dhaee|dhay)\s*(?:marla|marley|marle)\b", "marla", 2.5),
    (r"\b(?:aadha|adha)\s*(?:marla|marley|marle)\b", "marla", 0.5),
    (r"\b(?:paanch|panch)\s*(?:marla|marley|marle)\b", "marla", 5.0),
    (r"\b(?:das|dus)\s*(?:marla|marley|marle)\b", "marla", 10.0),
    (r"\b(?:bees|bis)\s*(?:marla|marley|marle)\b", "marla", 20.0),
    (r"\b(?:ek|aik|one)\s*kanal\b", "kanal", 1.0),
    (r"\b(?:do|two)\s*kanal\b", "kanal", 2.0),
    (r"\b(?:teen|three)\s*kanal\b", "kanal", 3.0),
    (r"\b(?:chaar|four)\s*kanal\b", "kanal", 4.0),
]


def parse_land_size(text: str) -> LandSizeResult | None:
    """Parse regional Pakistani land units (Marla, Kanal, Square Yards/Gaz, Sq Ft) into square feet."""
    lowered = text.casefold()

    # Check colloquial Urdu phrases
    for pattern, unit, quantity in COLLOQUIAL_UNITS:
        if re.search(pattern, lowered):
            if unit == "kanal":
                sqft = int(quantity * SQFT_PER_KANAL)
            else:
                sqft = int(quantity * SQFT_PER_MARLA)
            return {
                "size_sqft": sqft,
                "unit": unit,
                "quantity": quantity,
                "formatted": format_land_size(sqft, unit, quantity),
            }

    # Kanal match
    kanal_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:kanal|kanals|knl)\b", lowered)
    if kanal_match:
        quantity = float(kanal_match.group(1))
        sqft = int(quantity * SQFT_PER_KANAL)
        return {
            "size_sqft": sqft,
            "unit": "kanal",
            "quantity": quantity,
            "formatted": format_land_size(sqft, "kanal", quantity),
        }

    # Marla match
    marla_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:marla|marlas|marley|marle|mrla)\b", lowered)
    if marla_match:
        quantity = float(marla_match.group(1))
        sqft = int(quantity * SQFT_PER_MARLA)
        return {
            "size_sqft": sqft,
            "unit": "marla",
            "quantity": quantity,
            "formatted": format_land_size(sqft, "marla", quantity),
        }

    # Gaz / Square Yard match
    gaz_match = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:gaz|guz|sq\s*yds?|square\s*yards?|sq\s*yard)\b", lowered
    )
    if gaz_match:
        quantity = float(gaz_match.group(1))
        sqft = int(quantity * SQFT_PER_GAZ)
        return {
            "size_sqft": sqft,
            "unit": "gaz",
            "quantity": quantity,
            "formatted": format_land_size(sqft, "gaz", quantity),
        }

    # Explicit sq ft match
    sqft_match = re.search(
        r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(?:sq\s*ft|sqft|square\s*feet|sq\s*feet|foot)\b",
        lowered,
    )
    if sqft_match:
        quantity = float(sqft_match.group(1).replace(",", ""))
        sqft = int(quantity)
        return {
            "size_sqft": sqft,
            "unit": "sqft",
            "quantity": quantity,
            "formatted": f"{sqft:,} sq ft",
        }

    return None


def format_land_size(sqft: int, unit: str | None = None, quantity: float | None = None) -> str:
    """Format land size with Pakistani unit equivalence."""
    if unit == "kanal" and quantity is not None:
        q_str = f"{quantity:g}"
        return f"{sqft:,} sq ft ({q_str} Kanal / {int(quantity * 20)} Marla)"
    if unit == "marla" and quantity is not None:
        q_str = f"{quantity:g}"
        return f"{sqft:,} sq ft ({q_str} Marla)"
    if unit == "gaz" and quantity is not None:
        q_str = f"{quantity:g}"
        return f"{sqft:,} sq ft ({q_str} Gaz / Sq Yds)"

    # Auto equivalence
    if sqft >= SQFT_PER_KANAL and sqft % SQFT_PER_KANAL == 0:
        kanals = sqft // SQFT_PER_KANAL
        return f"{sqft:,} sq ft ({kanals} Kanal)"
    if sqft >= SQFT_PER_MARLA and sqft % SQFT_PER_MARLA == 0:
        marlas = sqft // SQFT_PER_MARLA
        return f"{sqft:,} sq ft ({marlas} Marla)"
    if sqft >= 900 and sqft % SQFT_PER_GAZ == 0:
        gaz = sqft // SQFT_PER_GAZ
        return f"{sqft:,} sq ft ({gaz} Gaz)"
    return f"{sqft:,} sq ft"


def explain_land_conversion(text: str) -> str | None:
    """Detect queries asking for land unit conversions and return clear explanations."""
    lowered = text.casefold()
    conversion_keywords = ("kitne", "kitna", "how many", "convert", "barabar", "equal", "difference", "farq")
    if not any(k in lowered for k in conversion_keywords):
        return None

    if "marla" in lowered and ("sqft" in lowered or "square feet" in lowered or "feet" in lowered):
        return (
            "Pakistan mein standard residential housing societies (DHA, Bahria Town waghera) mein "
            "1 Marla = 225 square feet hota hai. "
            "Old revenue records mein 1 Marla = 272 sq ft bhi count hota tha. "
            "5 Marla taqreeban 1,125 sq ft banta hai, aur 10 Marla = 2,250 sq ft hota hai."
        )

    if "kanal" in lowered and ("marla" in lowered or "sqft" in lowered or "feet" in lowered):
        return (
            "1 Kanal mein 20 Marlas hotay hain. "
            "Standard measurement ke mutabiq 1 Kanal = 4,500 square feet (ya taqreeban 500 square yards / gaz) hota hai. "
            "2 Kanal taqreeban 9,000 square feet banta hai."
        )

    if ("gaz" in lowered or "square yard" in lowered) and ("sqft" in lowered or "feet" in lowered or "marla" in lowered):
        return (
            "1 Square Yard (Gaz / گز) = 9 square feet hota hai. "
            "Karachi mein plots aam tor par gaz mein measure hotay hain jaise 120 Gaz (1,080 sq ft), "
            "240 Gaz (2,160 sq ft), aur 500 Gaz (4,500 sq ft = 1 Kanal)."
        )

    return None
