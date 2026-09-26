from __future__ import annotations

import re

# Domain-specific Pakistani real estate authorities and regulatory abbreviations
AUTHORITY_REPLACEMENTS = {
    r"\bSBCA\b": "S B C A",
    r"\bCDA\b": "C D A",
    r"\bLDA\b": "L D A",
    r"\bRDA\b": "R D A",
    r"\bFDA\b": "F D A",
    r"\bKDA\b": "K D A",
    r"\bFBR\b": "F B R",
    r"\bNOC\b": "N O C",
    r"\bCVT\b": "C V T",
}

# Tax sections common in Pakistani property transactions
TAX_SECTION_REPLACEMENTS = [
    (re.compile(r"\b236-?[Kk]\b"), "236 K"),
    (re.compile(r"\b236-?[Cc]\b"), "236 C"),
    (re.compile(r"\b(?:section\s*)?7-?[Ee]\b", re.IGNORECASE), "Section 7 E"),
]

# Pakistani road and locality hyphenation normalization to prevent neural TTS pauses
LOCALITY_PATTERNS = [
    (re.compile(r"\bKhayaban-e-([A-Za-z]+)\b", re.IGNORECASE), r"Khayaban e \1"),
    (re.compile(r"\bShahrah-e-([A-Za-z]+)\b", re.IGNORECASE), r"Shahrah e \1"),
    (re.compile(r"\bSector\s+([A-Za-z])-(\d{1,2})\b", re.IGNORECASE), r"Sector \1 \2"),
    (re.compile(r"\b([A-Za-z])-(\d{1,2})\b"), r"\1 \2"),
]

# Real estate units and measurement expansions
UNIT_REPLACEMENTS = [
    (re.compile(r"\bsq\.?\s*ft\.?\b", re.IGNORECASE), "square feet"),
    (re.compile(r"\bsqft\b", re.IGNORECASE), "square feet"),
    (re.compile(r"\bsq\.?\s*yd\.?\b", re.IGNORECASE), "square yards"),
    (re.compile(r"\bsqyd\b", re.IGNORECASE), "square yards"),
]

CURRENCY_REGEX = re.compile(
    r"\b(?:PKR|Rs\.?)\s*(\d+(?:\.\d+)?)\s*(crore|cr|lakh|lac|lacs|thousand)\b",
    re.IGNORECASE,
)


def _currency_sub(match: re.Match[str]) -> str:
    amount = match.group(1)
    unit = match.group(2).lower()
    if unit in ("cr", "crore"):
        unit_str = "crore"
    elif unit in ("lac", "lacs", "lakh"):
        unit_str = "lakh"
    else:
        unit_str = unit
    return f"{amount} {unit_str} rupay"


def apply_phonetic_transliteration(text: str, target_provider: str = "generic") -> str:
    """Normalize Pakistani real estate entities, acronyms, and locality terms for natural neural TTS.

    Standard multilingual neural models (Fish Audio, ElevenLabs, OpenAI) frequently stumble on
    hyphenated Urdu-Persian compounds (e.g. Khayaban-e-Bukhari), regulatory abbreviations (SBCA, CDA, FBR),
    and local land measurements. This normalizer prepares clean, pronouncible text without altering semantic meaning.
    """
    if not text or not text.strip():
        return text

    normalized = text

    # 1. Authority acronyms
    for pattern, replacement in AUTHORITY_REPLACEMENTS.items():
        normalized = re.sub(pattern, replacement, normalized)

    # 2. Tax sections
    for regex, replacement in TAX_SECTION_REPLACEMENTS:
        normalized = regex.sub(replacement, normalized)

    # 3. Localities, roads, and sector designations
    for regex, replacement in LOCALITY_PATTERNS:
        normalized = regex.sub(replacement, normalized)

    # 4. Units
    for regex, replacement in UNIT_REPLACEMENTS:
        normalized = regex.sub(replacement, normalized)

    # 5. Currency
    normalized = CURRENCY_REGEX.sub(_currency_sub, normalized)

    # 6. Provider-specific tweaks if required
    if target_provider == "fish":
        normalized = re.sub(r"[*_#`~]+", "", normalized)

    # Clean double spaces
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized
