from __future__ import annotations

import re
from typing import TypedDict


class TaxCalculation(TypedDict):
    price_pkr: int
    is_filer: bool
    transaction_type: str
    province: str
    fbr_section: str
    fbr_rate_percent: float
    fbr_tax_pkr: int
    provincial_rate_percent: float
    provincial_fees_pkr: int
    total_tax_fees_pkr: int
    total_cost_pkr: int
    breakdown_text: str


def calculate_property_taxes(
    price_pkr: int,
    is_filer: bool = True,
    transaction_type: str = "buy",
    province: str = "punjab",
) -> TaxCalculation:
    """Calculate verified Pakistani real estate transaction taxes (FBR Sections 236K/236C & Provincial Duties).

    Based on the latest FBR Finance Act provisions and Provincial Board of Revenue schedules.
    """
    transaction_type = transaction_type.lower()
    province = province.lower()

    # 1. Federal Advance Tax (Section 236K for Buyer, Section 236C for Seller)
    if transaction_type in ("buy", "purchase", "kharidari"):
        fbr_section = "Section 236K (Advance Tax on Purchase)"
        if is_filer:
            if price_pkr <= 50_000_000:
                fbr_rate = 3.0
            elif price_pkr <= 100_000_000:
                fbr_rate = 3.5
            else:
                fbr_rate = 4.0
        else:
            if price_pkr <= 50_000_000:
                fbr_rate = 10.5
            elif price_pkr <= 100_000_000:
                fbr_rate = 12.0
            else:
                fbr_rate = 15.0
    else:  # Sale
        fbr_section = "Section 236C (Advance Tax on Sale)"
        fbr_rate = 3.0 if is_filer else 10.0

    fbr_tax_pkr = int(price_pkr * (fbr_rate / 100.0))

    # 2. Provincial Transfer Duties (Stamp Duty, TMA, Registration Fee)
    if "sindh" in province or "karachi" in province:
        provincial_rate = 3.0  # 2% Stamp Duty + 1% Town Tax (TMA)
        prov_name = "Sindh (SBOR & TMA)"
    elif "islamabad" in province or "cda" in province or "ict" in province:
        provincial_rate = 2.5  # 1.5% CDA Transfer + 1% ICT Stamp Duty
        prov_name = "Islamabad (CDA / ICT)"
    else:  # Punjab (Lahore, Rawalpindi, Multan)
        provincial_rate = 2.0  # 1% Stamp Duty (PRA) + 1% TMA Municipal Fee
        prov_name = "Punjab (BOR & TMA)"

    provincial_fees_pkr = int(price_pkr * (provincial_rate / 100.0))
    total_tax_fees_pkr = fbr_tax_pkr + provincial_fees_pkr
    total_cost_pkr = price_pkr + total_tax_fees_pkr if "buy" in transaction_type else price_pkr - total_tax_fees_pkr

    status_str = "Active Taxpayer (Filer)" if is_filer else "Non-Filer"
    action_str = "Kharidari (Purchase)" if "buy" in transaction_type else "Frosh (Sale)"

    breakdown = (
        f"PKR {price_pkr:,} property par {status_str} ke mutabiq {action_str} tax calculation:\n"
        f"1. FBR {fbr_section}: {fbr_rate}% = PKR {fbr_tax_pkr:,}\n"
        f"2. {prov_name} Transfer Duties: {provincial_rate}% = PKR {provincial_fees_pkr:,}\n"
        f"Total Govt Taxes & Duties: PKR {total_tax_fees_pkr:,} ({fbr_rate + provincial_rate}%). "
        f"Estimated Total Net: PKR {total_cost_pkr:,}."
    )

    return {
        "price_pkr": price_pkr,
        "is_filer": is_filer,
        "transaction_type": transaction_type,
        "province": province,
        "fbr_section": fbr_section,
        "fbr_rate_percent": fbr_rate,
        "fbr_tax_pkr": fbr_tax_pkr,
        "provincial_rate_percent": provincial_rate,
        "provincial_fees_pkr": provincial_fees_pkr,
        "total_tax_fees_pkr": total_tax_fees_pkr,
        "total_cost_pkr": total_cost_pkr,
        "breakdown_text": breakdown,
    }


def explain_tax_query(text: str, detected_price: int | None = None) -> str | None:
    """Analyze real estate taxation questions and provide deterministic FBR/Provincial advice."""
    lowered = text.casefold()
    tax_keywords = ("tax", "taxes", "fbr", "filer", "non-filer", "non filer", "236k", "236c", "stamp duty", "transfer fee", "cgt")
    if not any(k in lowered for k in tax_keywords):
        return None

    # Determine filer vs non-filer
    is_filer = not ("non-filer" in lowered or "non filer" in lowered or "late filer" in lowered)
    is_sale = any(k in lowered for k in ("bechna", "sale", "selling", "frosh", "seller", "236c"))
    tx_type = "sale" if is_sale else "buy"

    # Determine province / city
    province = "punjab"
    if "karachi" in lowered or "sindh" in lowered or "clifton" in lowered:
        province = "sindh"
    elif "islamabad" in lowered or "cda" in lowered or "blue area" in lowered:
        province = "islamabad"

    # If price was detected or present in text
    price = detected_price
    if price is None:
        # Check if price exists in query e.g. "1 crore" or "2 crore"
        crore_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:crore|cr)\b", lowered)
        if crore_match:
            price = int(float(crore_match.group(1)) * 10_000_000)
        lakh_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:lakh|lac)\b", lowered)
        if lakh_match and price is None:
            price = int(float(lakh_match.group(1)) * 100_000)

    if price and price >= 1_000_000:
        calc = calculate_property_taxes(price, is_filer=is_filer, transaction_type=tx_type, province=province)
        return calc["breakdown_text"]

    # General tax explanation
    if "236k" in lowered or "purchase tax" in lowered or "kharidne" in lowered:
        return (
            "FBR Section 236K ke tehat property khareedne par advance tax lagta hai: "
            "Filers ke liye yeh 3% (up to 5 Crore), 3.5% (5-10 Crore), aur 4% (above 10 Crore) hai. "
            "Non-filers ke liye yeh tax 10.5% se 15% tak barh jata hai. "
            "Iske ilawa 2% se 3% provincial stamp duty aur TMA charges alag se hotay hain."
        )

    if "236c" in lowered or "sale tax" in lowered or "bechne" in lowered:
        return (
            "FBR Section 236C ke mutabiq property bechte waqt seller par advance tax lagta hai: "
            "Active Taxpayers (Filers) ke liye 3% rate hai, jabke Non-Filers ke liye 10% advance tax deduct hota hai. "
            "Agar holding period complete ho to Capital Gains Tax (CGT) exemption bhi milti hai."
        )

    return (
        "Pakistan Real Estate Tax Guidelines:\n"
        "1. Buyer Advance Tax (Section 236K): Filer ke liye 3%, Non-Filer ke liye 10.5% - 15%.\n"
        "2. Seller Advance Tax (Section 236C): Filer ke liye 3%, Non-Filer ke liye 10%.\n"
        "3. Provincial Transfer & Stamp Duty: Punjab mein 2%, Sindh (Karachi) mein 3%, Islamabad mein 2.5%.\n"
        "Aap kisi specific property amount (jaise 2 Crore ya 50 Lakh) par exact tax calculate karwana chahein to batayein."
    )
