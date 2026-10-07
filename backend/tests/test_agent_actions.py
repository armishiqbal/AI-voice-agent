from app.agents.graph import EstateAgent
from app.domain.fixtures import demo_properties
from app.services.appointments import PropertyRepository as EmptyByDefaultPropertyRepository


class PropertyRepository(EmptyByDefaultPropertyRepository):
    def __init__(self) -> None:
        super().__init__(demo_properties())


def test_agent_calculates_mortgage_action():
    agent = EstateAgent(PropertyRepository())
    decision = agent.respond(
        "conv-mortgage-1",
        "Calculate mortgage for 5 crore with 20% down payment over 15 years",
        language="en",
    )
    assert decision.kind == "execute_action"
    assert len(decision.actions) == 1
    action = decision.actions[0]
    assert action.kind == "calculate_mortgage"
    assert action.payload["property_price_pkr"] == 50_000_000
    assert action.payload["down_payment_pct"] == 20
    assert action.payload["tenure_years"] == 15
    assert action.payload["estimated_monthly_payment_pkr"] > 0
    assert "breakdown" in decision.spoken_text.lower() or "installment" in decision.spoken_text.lower()


def test_agent_shortlist_property_action():
    agent = EstateAgent(PropertyRepository())
    # First get a recommendation to populate selected properties
    agent.respond("conv-shortlist-1", "Mera budget 3 crore hai Karachi mein buy karna hai")
    # Now save to shortlist
    decision = agent.respond("conv-shortlist-1", "Save this property to my shortlist", language="en")
    assert decision.kind == "execute_action"
    assert len(decision.actions) == 1
    action = decision.actions[0]
    assert action.kind == "shortlist_property"
    assert action.payload["action"] == "add"
    assert "shortlist" in decision.spoken_text.lower()


def test_agent_navigation_action():
    agent = EstateAgent(PropertyRepository())
    decision = agent.respond("conv-nav-1", "Open catalog page", language="en")
    assert decision.kind == "execute_action"
    assert len(decision.actions) == 1
    action = decision.actions[0]
    assert action.kind == "navigate_to"
    assert action.payload["path"] == "/catalog"
    assert "catalog" in decision.spoken_text.lower()


def test_agent_attaches_filter_catalog_to_recommendation():
    agent = EstateAgent(PropertyRepository())
    decision = agent.respond("conv-filter-1", "Mera budget 3 crore hai Karachi mein buy karna hai")
    assert decision.kind == "recommend"
    filter_actions = [a for a in decision.actions if a.kind == "filter_catalog"]
    assert len(filter_actions) == 1
    assert filter_actions[0].payload["city"] == "Karachi"
