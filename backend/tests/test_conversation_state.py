from app.agents.graph import ConversationState
from app.domain.models import Intent
from app.repositories.bootstrap import create_schema_for_local_development
from app.repositories.conversation_state import ConversationStateStore
from app.repositories.database import Base, SessionLocal, engine
from app.repositories.records import ConversationStateRecord


def test_conversation_state_store_round_trips_langgraph_state() -> None:
    create_schema_for_local_development()
    store = ConversationStateStore()
    original = ConversationState(
        history=["Karachi buy"],
        detected_language="ur-Latn",
        budget=30_000_000,
        city="Karachi",
        bedrooms=3,
        amenities=["parking"],
        investment_goal="capital appreciation",
        intent=Intent.BUY,
        selected_property_ids=["DEMO-001"],
        retrieved_sources=["DEMO-001:demo-v1"],
        tool_results={"property_search": {"count": 1, "source": "sql"}},
    )
    store.save("persistent-conversation", original)
    loaded = store.load("persistent-conversation")
    assert loaded is not None
    assert loaded["city"] == "Karachi"
    assert loaded["selected_property_ids"] == ["DEMO-001"]
    assert loaded["bedrooms"] == 3
    assert loaded["amenities"] == ["parking"]
    assert loaded["investment_goal"] == "capital appreciation"
    assert loaded["tool_results"]["property_search"]["source"] == "sql"
    assert loaded["intent"] == "buy"
    with SessionLocal() as session:
        record = session.get(ConversationStateRecord, "persistent-conversation")
    assert record is not None and record.expires_at is not None
    Base.metadata.drop_all(bind=engine)
