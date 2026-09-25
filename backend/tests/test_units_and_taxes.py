from __future__ import annotations

import pytest

from app.agents.graph import EstateAgent
from app.domain.fixtures import demo_properties
from app.domain.legal import verify_legal_status
from app.domain.taxes import calculate_property_taxes, explain_tax_query
from app.domain.units import explain_land_conversion, parse_land_size
from app.repositories.properties import SqlPropertyRepository


def test_parse_land_size_conversions() -> None:
    # 10 Marla = 2250 sqft
    ten_marla = parse_land_size("Mujhe 10 marla ka ghar chahiye DHA Lahore mein")
    assert ten_marla is not None
    assert ten_marla["unit"] == "marla"
    assert ten_marla["quantity"] == 10.0
    assert ten_marla["size_sqft"] == 2250

    # 1 Kanal = 4500 sqft
    one_kanal = parse_land_size("Looking for a 1 kanal villa")
    assert one_kanal is not None
    assert one_kanal["unit"] == "kanal"
    assert one_kanal["quantity"] == 1.0
    assert one_kanal["size_sqft"] == 4500

    # 240 Gaz = 2160 sqft
    gaz = parse_land_size("240 gaz ka plot Clifton Karachi")
    assert gaz is not None
    assert gaz["unit"] == "gaz"
    assert gaz["size_sqft"] == 2160

    # Colloquial dedh kanal = 1.5 kanal = 6750 sqft
    dedh_kanal = parse_land_size("dedh kanal ka bangla")
    assert dedh_kanal is not None
    assert dedh_kanal["quantity"] == 1.5
    assert dedh_kanal["size_sqft"] == 6750


def test_explain_land_conversion() -> None:
    res = explain_land_conversion("10 marla mein kitne square feet hotay hain?")
    assert res is not None
    assert "225 square feet" in res
    assert "2,250 sq ft" in res

    kanal_res = explain_land_conversion("1 kanal mein kitne marla hotay hain?")
    assert kanal_res is not None
    assert "20 Marlas" in kanal_res


def test_calculate_property_taxes_filer_vs_non_filer() -> None:
    # 2 Crore buyer filer
    filer_tax = calculate_property_taxes(20_000_000, is_filer=True, transaction_type="buy", province="punjab")
    assert filer_tax["fbr_rate_percent"] == 3.0
    assert filer_tax["fbr_tax_pkr"] == 600_000
    assert filer_tax["provincial_rate_percent"] == 2.0
    assert filer_tax["provincial_fees_pkr"] == 400_000
    assert filer_tax["total_tax_fees_pkr"] == 1_000_000

    # 2 Crore buyer non-filer
    non_filer_tax = calculate_property_taxes(20_000_000, is_filer=False, transaction_type="buy", province="punjab")
    assert non_filer_tax["fbr_rate_percent"] == 10.5
    assert non_filer_tax["fbr_tax_pkr"] == 2_100_000

    # Seller tax (Section 236C)
    seller_tax = calculate_property_taxes(30_000_000, is_filer=True, transaction_type="sale", province="sindh")
    assert seller_tax["fbr_section"] == "Section 236C (Advance Tax on Sale)"
    assert seller_tax["fbr_rate_percent"] == 3.0


def test_explain_tax_query() -> None:
    res = explain_tax_query("filer ko 2 crore ke flat par kitna tax dena hoga?")
    assert res is not None
    assert "236K" in res
    assert "PKR 20,000,000" in res

    general = explain_tax_query("property tax rules in pakistan for filer and non filer")
    assert general is not None
    assert "236K" in general
    assert "236C" in general


def test_legal_noc_verification() -> None:
    sbca = verify_legal_status("kya clifton ka project approved hai?", "Clifton Sea View")
    assert sbca is not None
    assert "SBCA" in sbca
    assert "APPROVED" in sbca

    cda = verify_legal_status("is blue area commercial office approved by CDA?", "Blue Area")
    assert cda is not None
    assert "CDA" in cda
    assert "APPROVED" in cda


def test_agent_answers_domain_questions() -> None:
    props = demo_properties()

    class FakeRepo:
        def list(self, query=None):
            return props

        def get_available(self, pid):
            return next((p for p in props if p.id == pid), None)

    agent = EstateAgent(properties=FakeRepo())

    # Tax question
    tax_decision = agent.respond("conv-1", "filer ke liye property purchase par kitna FBR tax lagta hai?")
    assert tax_decision.kind == "answer"
    assert "236K" in tax_decision.spoken_text or "Filer" in tax_decision.spoken_text

    # Land conversion question
    conv_decision = agent.respond("conv-2", "1 kanal mein kitne square feet hotay hain?")
    assert conv_decision.kind == "answer"
    assert "4,500" in conv_decision.spoken_text

    # Legal question
    legal_decision = agent.respond("conv-3", "kya clifton project SBCA se approved hai?")
    assert legal_decision.kind == "answer"
    assert "SBCA" in legal_decision.spoken_text


def test_score_lead_temperature() -> None:
    from app.domain.scoring import score_lead

    # High-value buyer with booked visit
    hot = score_lead(budget_pkr=25_000_000, intent="buy", booked_visit=True, history=["urgent need house this week"])
    assert hot["temperature"] == "hot"
    assert hot["score"] >= 75

    # Early browser without budget or visit
    cold = score_lead(budget_pkr=None, intent="unknown", booked_visit=False, history=["just looking"])
    assert cold["temperature"] == "cold"
    assert cold["score"] < 35
