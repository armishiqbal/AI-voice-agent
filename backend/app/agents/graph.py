from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from time import perf_counter
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.prompts import answer_prompt, general_qa_prompt, recommendation_prompt
from app.core.observability import TraceStore
from app.domain.legal import verify_legal_status
from app.domain.models import AgentAction, AgentDecision, Intent, PropertyQuery
from app.domain.scoring import score_lead
from app.domain.taxes import explain_tax_query
from app.domain.units import explain_land_conversion, parse_land_size
from app.integrations.llm import LLMDecisionError, StructuredDecisionProvider
from app.services.appointments import redact_for_retention
from app.services.retrieval import GroundedRetriever, rank_properties

INJECTION_PATTERNS = (
    "ignore previous",
    "ignore instructions",
    "ignore all instructions",
    "disregard instructions",
    "reveal your prompt",
    "system prompt",
    "internal company data",
    "book fake",
)


def _normalize_voice_text(text: str) -> str:
    """Normalize Arabic-script marks that STT may add around Urdu loanwords."""
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return "".join(
        character
        for character in normalized
        if not unicodedata.combining(character) and character != "\u0640"
    )


@dataclass
class ConversationState:
    history: list[str] = field(default_factory=list)
    detected_language: str = "en"
    lead_profile: dict[str, str] = field(default_factory=dict)
    budget: int | None = None
    city: str | None = None
    area: str | None = None
    bedrooms: int | None = None
    target_size_sqft: int | None = None
    land_unit: str | None = None
    amenities: list[str] = field(default_factory=list)
    investment_goal: str | None = None
    intent: Intent = Intent.UNKNOWN
    retrieved_sources: list[str] = field(default_factory=list)
    selected_property_ids: list[str] = field(default_factory=list)
    tool_results: dict[str, object] = field(default_factory=dict)
    appointment_status: str | None = None
    escalation_reason: str | None = None


class GraphState(TypedDict, total=False):
    conversation_id: str
    text: str
    language: str
    blocked: bool
    intent: str
    decision: AgentDecision
    route: str


class EstateAgent:
    """Deterministic safe-path LangGraph orchestrator with optional durable state."""

    def __init__(
        self,
        properties: object,
        traces: TraceStore | None = None,
        decision_provider: StructuredDecisionProvider | None = None,
        state_store: object | None = None,
    ) -> None:
        self.properties = properties
        self.states: dict[str, ConversationState] = {}
        self.traces = traces or TraceStore()
        self.decision_provider = decision_provider
        self.state_store = state_store
        self.retriever = GroundedRetriever()
        builder = StateGraph(GraphState)
        builder.add_node("guardrails", self._guardrails)
        builder.add_node("intent_detection", self._detect_intent)
        builder.add_node("grounded_resolution", self._resolve)
        builder.add_node("grounding_validation", self._validate_grounding)
        for route_name in (
            "greeting",
            "answer",
            "ask_clarification",
            "recommend",
            "book",
            "reschedule",
            "cancel",
            "handoff",
            "goodbye",
            "execute_action",
        ):
            builder.add_node(route_name, self._route_node)
        builder.add_edge(START, "guardrails")
        builder.add_conditional_edges(
            "guardrails",
            lambda state: "handoff" if state["blocked"] else "intent_detection",
            {"handoff": "handoff", "intent_detection": "intent_detection"},
        )
        builder.add_edge("intent_detection", "grounded_resolution")
        builder.add_edge("grounded_resolution", "grounding_validation")
        builder.add_conditional_edges(
            "grounding_validation",
            lambda state: state["route"],
            {
                route_name: route_name
                for route_name in (
                    "greeting",
                    "answer",
                    "ask_clarification",
                    "recommend",
                    "book",
                    "reschedule",
                    "cancel",
                    "handoff",
                    "goodbye",
                    "execute_action",
                )
            },
        )
        for route_name in (
            "greeting",
            "answer",
            "ask_clarification",
            "recommend",
            "book",
            "reschedule",
            "cancel",
            "handoff",
            "goodbye",
            "execute_action",
        ):
            builder.add_edge(route_name, END)
        self.graph = builder.compile()

    def _guardrails(self, graph_state: GraphState) -> dict[str, object]:
        started = perf_counter()
        text = graph_state["text"].lower()
        blocked = any(pattern in text for pattern in INJECTION_PATTERNS)
        result: dict[str, object] = {"blocked": blocked}
        if blocked:
            result["decision"] = AgentDecision(
                kind="handoff",
                reason="guardrail",
                spoken_text="Main internal instructions ya private data share nahi kar sakta. Main verified property options mein help kar sakta hoon.",
            )
            result["route"] = "handoff"
        self.traces.record(
            graph_state["conversation_id"], "guardrails", started, "blocked" if blocked else "ok"
        )
        return result

    def _detect_intent(self, graph_state: GraphState) -> dict[str, object]:
        started = perf_counter()
        intent = self._intent(graph_state["text"])
        self.traces.record(graph_state["conversation_id"], "intent_detection", started)
        return {"intent": intent.value}

    def _resolve(self, graph_state: GraphState) -> dict[str, object]:
        started = perf_counter()
        text = graph_state["text"]
        lowered = text.casefold().strip()
        if self._is_goodbye(lowered):
            decision = AgentDecision(
                kind="answer",
                spoken_text="Allah hafiz. Jab bhi verified property ya visit ki zaroorat ho, Awaaz Estate se rabta kijiye.",
            )
            route = "goodbye"
        elif self._is_greeting(lowered) and Intent(graph_state["intent"]) == Intent.UNKNOWN and len(lowered.split()) <= 5:
            decision = AgentDecision(
                kind="ask_clarification",
                spoken_text="Assalam-o-Alaikum. Main Awaaz Estate se hoon. Aap buy, rent, commercial, ya investment ke liye dekh rahe hain?",
            )
            route = "greeting"
        else:
            decision = self._decide(
                graph_state["conversation_id"],
                text,
                Intent(graph_state["intent"]),
                graph_state.get("language", "en"),
            )
            route = decision.kind
        self.traces.record(
            graph_state["conversation_id"], "grounded_resolution", started, decision.kind
        )
        return {"decision": decision, "route": route}

    def _validate_grounding(self, graph_state: GraphState) -> dict[str, object]:
        """Recheck authoritative inventory immediately before exposing a decision.

        This is an executable graph boundary, separate from model resolution.
        Appointment commands still require service-side consent and slot checks.
        """
        started = perf_counter()
        decision = graph_state["decision"]
        available = all(self.properties.get_available(item) is not None for item in decision.property_ids)
        if not available:
            decision = AgentDecision(
                kind="ask_clarification", reason="inventory_changed",
                spoken_text="Yeh option ab available nahi hai. Kya main fresh options check karoon?",
            )
            state = self.states.get(graph_state["conversation_id"])
            if state is not None:
                state.selected_property_ids = []
                if state.history and state.history[-1].startswith("Agent: "):
                    state.history[-1] = f"Agent: {decision.spoken_text}"
                if self.state_store is not None:
                    self.state_store.save(graph_state["conversation_id"], state)
        self.traces.record(graph_state["conversation_id"], "grounding_validation", started, "ok" if available else "inventory_changed")
        return {"decision": decision, "route": graph_state["route"] if available else decision.kind}

    def _route_node(self, graph_state: GraphState) -> dict[str, object]:
        """Explicit action nodes keep consequential routes visible in LangGraph traces."""
        route = graph_state.get("route")
        if route:
            self.traces.record(graph_state["conversation_id"], str(route), perf_counter())
        return {"decision": graph_state["decision"]}

    @staticmethod
    def _intent(text: str) -> Intent:
        value = _normalize_voice_text(text)
        if any(word in value for word in ("cancel", "radd", "cancel kar", "mansookh", "nahi chahiye visit")):
            return Intent.CANCEL
        if any(word in value for word in ("reschedule", "change time", "time change", "waqt badalna", "doosra time")):
            return Intent.RESCHEDULE
        explicit_visit_request = any(
            phrase in value
            for phrase in (
                "visit karna hai",
                "visit karni hai",
                "visit book kar",
                "site visit karna",
                "site visit karni",
                "appointment book kar",
                "appointment schedule kar",
                "appointment chahiye",
                "booking chahiye",
                "booking karni hai",
                "booking karna hai",
                "booking kar dein",
                "property dekhne jana",
                "ghar dekhne jana",
            )
        ) or any(
            re.search(pattern, value)
            for pattern in (
                r"\b(?:book|schedule|arrange|request|set up)\s+(?:a\s+|an\s+|the\s+)?(?:property\s+|site\s+)?(?:visit|viewing|appointment)\b",
                r"\b(?:property|site)\s+(?:visit|viewing)\s+(?:book|schedule|arrange)\b",
                r"\b(?:i want|i would like|i'd like|i need|can i|could i|let's|please)\s+(?:to\s+)?(?:visit|view|see)\b",
                r"\b(?:i want|i would like|i'd like|i need)\s+(?:a\s+|an\s+|the\s+)?(?:property\s+)?(?:visit|viewing|appointment)\b",
                r"\b(?:book|schedule|arrange|request)\b.{0,32}\b(?:visit|viewing|appointment)\b",
                r"\b(?:book|schedule)\s+(?:it|that|this)\b",
            )
        )
        if explicit_visit_request:
            return Intent.BOOK
        # A listing is an object being searched for; it does not imply that the caller
        # wants to sell. Require an explicit seller action to avoid routing buyer/renter
        # requests such as "show me available listings" to human seller intake.
        if any(
            phrase in value
            for phrase in (
                "sell my",
                "sell a property",
                "sell the property",
                "selling my",
                "selling a property",
                "list my property",
                "list my house",
                "list my apartment",
                "seller listing",
                "my listing",
                "put my property on the market",
                "bechna hai",
                "bechni hai",
                "bechna chahta",
                "bechna chahti",
                "bech raha",
                "bech rahi",
                "property bech",
                "ghar bech",
            )
        ) or re.search(r"\bsell\b", value):
            return Intent.SELL
        if any(word in value for word in ("investment", "invest ", "rental yield", "passive income")):
            return Intent.INVEST
        if any(
            word in value
            for word in (
                # Deepgram Urdu can render the spoken English "rent" as these
                # phonetic spellings in mixed-script UrduLish transcripts.
                "rent", "riend", "رینٹ", "رینت", "رنت", "رنٹ", "وینٹ", "kiraya", "kiraye", "kiraaye", "rental", "rent pe", "rent par",
                "rent ka", "monthly rent", "रेंट", "किराया", "किराए", "किराये",
                "کرایہ", "کرائے", "کرایے",
            )
        ):
            return Intent.RENT
        if any(word in value for word in ("commercial", "office", "shop", "dukan", "dukaan", "plaza", "warehouse", "godam")):
            return Intent.COMMERCIAL
        if any(word in value for word in ("invest", "investment", "roi", "passive income", "yield", "sarmayakari", "munafa")):
            return Intent.INVEST
        if any(word in value for word in ("buy", "kharid", "khareed", "खरीद", "खरीदना", "خرید", "خریدنا", "purchase", "plot", "flat", "flats", "home", "homes", "house", "houses", "makan", "makaan", "kothi", "bangla", "villa", "villas", "bungalow", "apartment", "apartments", "zameen", "file")) or any(
            phrase in value
            for phrase in (
                "available property",
                "find a property",
                "find an available property",
                "looking for a property",
                "property options",
                "property in ",
                "property under ",
            )
        ):
            return Intent.BUY
        return Intent.UNKNOWN

    @staticmethod
    def _extract_budget(lowered: str) -> int | None:
        spoken_numbers = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
            "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
            "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
            "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
            "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80,
            "ninety": 90, "gyarah": 11, "giyarah": 11, "barah": 12,
            "terah": 13, "chaudah": 14, "choudah": 14, "pandrah": 15,
            "solah": 16, "satrah": 17, "atharah": 18, "unnis": 19,
            "bees": 20, "tees": 30, "chalees": 40, "pachaas": 50,
            "pachas": 50, "saath": 60, "sattar": 70, "assi": 80, "nabbe": 90,
            "ek": 1, "aik": 1, "do": 2, "teen": 3,
            "char": 4, "chaar": 4, "paanch": 5, "panch": 5,
            # Common Nova-3 UrduLish rendering of spoken "paanch".
            "paunch": 5, "das": 10,
            "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पाँच": 5, "पांच": 5,
            "छह": 6, "छः": 6, "सात": 7, "आठ": 8, "नौ": 9, "दस": 10,
            "ایک": 1, "دو": 2, "تین": 3, "چار": 4, "پانچ": 5,
            "چھ": 6, "سات": 7, "آٹھ": 8, "نو": 9, "دس": 10,
            "گیارہ": 11, "بارہ": 12, "تیرہ": 13, "چودہ": 14, "پندرہ": 15,
            "سولہ": 16, "سترہ": 17, "اٹھارہ": 18, "انیس": 19, "بیس": 20,
            "تیس": 30, "چالیس": 40, "پچاس": 50, "ساٹھ": 60, "ستر": 70,
            "اسی": 80, "نوے": 90,
        }
        colloquial = [
            (r"\b(?:dedh|dehr|daydh)\s*(?:crore|cr)\b", 15_000_000),
            (r"\b(?:dhai|dhaee|dhay)\s*(?:crore|cr)\b", 25_000_000),
            (r"\b(?:aadha|adha)\s*(?:crore|cr)\b", 5_000_000),
            (r"\b(?:sawa)\s*(?:crore|cr)\b", 12_500_000),
            (r"\b(?:paunay?|pone)\s*(?:do)\s*(?:crore|cr)\b", 17_500_000),
            (r"\b(?:dedh|dehr)\s*(?:lakh|lac)\b", 150_000),
            (r"\b(?:dhai|dhaee)\s*(?:lakh|lac)\b", 250_000),
            (r"\b(?:aadha|adha)\s*(?:lakh|lac)\b", 50_000),
        ]
        for pattern, amount in colloquial:
            if re.search(pattern, lowered):
                return amount

        spoken_number_pattern = "|".join(
            sorted((re.escape(word) for word in spoken_numbers), key=len, reverse=True)
        )
        for unit, multiplier in (
            # Urdu speech recognition may fuse کروڑ ہے into one token.
            (r"crore|cr|करोड़|करोड|کروڑ|کھرورہائے|کھرورہے|کھرورہا|کھرور|کھرو", 10_000_000),
            (r"lakh|lac|lacs|लाख|لاکھ", 100_000),
        ):
            spoken_match = re.search(rf"\b({spoken_number_pattern})\s*(?:{unit})\b", lowered)
            if spoken_match:
                return spoken_numbers[spoken_match.group(1)] * multiplier

        crore_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:crore|cr)\b", lowered)
        if crore_match is None:
            crore_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:کروڑ|करोड़|करोड)(?:\b|$|[،,.!?؟])", lowered)
        if crore_match:
            return int(float(crore_match.group(1)) * 10_000_000)

        lakh_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:lakh|lac|lacs)\b", lowered)
        if lakh_match is None:
            lakh_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:لاکھ|लाख)(?:\b|$|[،,.!?؟])", lowered)
        if lakh_match:
            return int(float(lakh_match.group(1)) * 100_000)

        million_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:million|mil|m)\b", lowered)
        if million_match:
            return int(float(million_match.group(1)) * 1_000_000)

        thousand_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:hazar|hazaar|thousand|k)\b", lowered)
        if thousand_match:
            return int(float(thousand_match.group(1)) * 1_000)

        raw_match = re.search(r"\b(\d{1,3}(?:,\d{3})+|\d{5,9})\b", lowered)
        if raw_match and any(w in lowered for w in ("budget", "price", "pkr", "rupay", "rs", "tak")):
            raw_val = int(raw_match.group(1).replace(",", ""))
            if raw_val >= 10_000:
                return raw_val

        return None

    @staticmethod
    def _extract_bedrooms(lowered: str) -> int | None:
        bedroom_match = re.search(
            r"\b(\d+)\s*(?:bed|beds|bedroom|bedrooms|br|kamray|kamre|kamra)\b", lowered
        )
        if bedroom_match:
            return int(bedroom_match.group(1))
        word_beds = [
            (1, r"\b(?:ek|aik|one)\s*(?:bed|bedroom|kamr)"),
            (2, r"\b(?:do|two)\s*(?:bed|bedroom|kamr)"),
            (3, r"\b(?:teen|three)\s*(?:bed|bedroom|kamr)"),
            (4, r"\b(?:chaar|char|four)\s*(?:bed|bedroom|kamr)"),
            (5, r"\b(?:paanch|panch|five)\s*(?:bed|bedroom|kamr)"),
        ]
        for num, pattern in word_beds:
            if re.search(pattern, lowered):
                return num
        return None

    @staticmethod
    def _extract_city(lowered: str) -> str | None:
        cities = {
            "Karachi": ("karachi", "کراچی", "कराची"),
            "Lahore": ("lahore", "لاہور", "लाहौर"),
            "Islamabad": ("islamabad", "اسلام آباد", "اسلاماباد", "इस्लामाबाद"),
            "Rawalpindi": ("rawalpindi", "راولپنڈی", "راولپِنڈی", "रावलपिंडी"),
            "Faisalabad": ("faisalabad", "فیصل آباد", "फैसलाबाद"),
            "Multan": ("multan", "ملتان", "मुल्तान"),
            "Peshawar": ("peshawar", "پشاور", "पेशावर"),
            "Quetta": ("quetta", "کوئٹہ", "क्वेटा"),
            "Gwadar": ("gwadar", "گوادر", "ग्वादर"),
            "Hyderabad": ("hyderabad", "حیدرآباد", "हैदराबाद"),
            "Sialkot": ("sialkot", "سیالکوٹ", "सियालकोट"),
            "Gujranwala": ("gujranwala", "گوجرانوالہ", "गुजरांवाला"),
            "Abbottabad": ("abbottabad", "ایبٹ آباد", "ایبٹاباد", "ایبٹ آباد"),
            "Bahawalpur": ("bahawalpur", "بہاولپور", "बہاولپور"),
            "Sargodha": ("sargodha", "سرگودھا", "سرگودها"),
        }
        for canonical, aliases in cities.items():
            if any(re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", lowered) for alias in aliases):
                return canonical
        return None

    @staticmethod
    def _is_unqualified_home_request(text: str) -> bool:
        # STT can code-switch scripts within a single UrduLish phrase (e.g.
        # Urdu-script "گھر" followed by Devanagari "चाहिए"). Match the
        # property and request words independently instead of requiring one
        # exact same-script phrase.
        property_markers = (
            "ghar", "گھر", "گار", "घर", "makan", "makaan", "مکان", "मकान",
            "house", "home", "property",
        )
        request_markers = (
            "\u091a\u093e\u0939\u093f\u090f",
            "chahiye", "chahie", "چاہیے", "چاہیئے", "چہ آئے", "चاہिए", "चाहिये",
            "چاہتا ہوں", "چاہتی ہوں", "चाहता हूं", "चाहती हूं",
        )
        return any(marker in text for marker in property_markers) and any(
            marker in text for marker in request_markers
        )

    @staticmethod
    def _extract_area(lowered: str) -> str | None:
        area_aliases = (
            ("dha phase 6", ("dha phase 6", "ڈی ایچ اے فیز 6", "ڈی ایچ اے فیز ۶", "ڈی ایچ اے فیز چھ")),
            ("dha phase 5", ("dha phase 5", "ڈی ایچ اے فیز 5", "ڈی ایچ اے فیز ۵", "ڈی ایچ اے فیز پانچ")),
            ("dha phase 2", ("dha phase 2", "ڈی ایچ اے فیز 2", "ڈی ایچ اے فیز ۲", "ڈی ایچ اے فیز دو")),
            (
                "dha",
                ("dha", "ڈی ایچ اے", "डीएचए", "डी एच ए", "t ah ah min"),
            ),
            ("clifton", ("clifton", "کلفٹن", "क्लिफ्टन")),
            ("gulberg", ("gulberg", "گلبرگ", "गुलबर्ग")),
            ("f-11", ("f-11", "ایف 11", "ایف-11")),
            ("bahria town", ("bahria town", "بحریہ ٹاؤن", "बहरिया टाउन")),
            ("bahria enclave", ("bahria enclave", "بحریہ انکلیو")),
            ("bahria orchard", ("bahria orchard", "بحریہ آرچرڈ")),
            ("bahria", ("bahria", "بحریہ")),
            ("blue area", ("blue area", "بلو ایریا")),
            ("gulshan-e-iqbal", ("gulshan-e-iqbal", "گلشن اقبال")),
            ("gulshan", ("gulshan", "گلشن")),
            ("pechs", ("pechs", "پی ای سی ایچ ایس")),
            ("cantt", ("cantt", "کینٹ")),
            ("johar town", ("johar town", "جوہر ٹاؤن")),
            ("johar", ("johar", "جوہر")),
            ("model town", ("model town", "ماڈل ٹاؤن")),
            ("e-11", ("e-11", "ای 11", "ای-11")),
            ("g-11", ("g-11", "جی 11", "جی-11")),
            ("f-7", ("f-7", "ایف 7", "ایف-7")),
            ("f-8", ("f-8", "ایف 8", "ایف-8")),
            ("f-10", ("f-10", "ایف 10", "ایف-10")),
            ("i-8", ("i-8", "آئی 8", "آئی-8")),
            ("askari", ("askari", "عسکری")),
            ("wapda town", ("wapda town", "واپڈا ٹاؤن")),
        )
        for area, aliases in area_aliases:
            if any(alias in lowered for alias in aliases):
                return area
        return None

    def _extract_mortgage_action(self, text: str, state: ConversationState) -> AgentAction | None:
        lowered = text.lower()
        mortgage_keywords = (
            "mortgage", "installment", "installments", "kist", "kisht", "loan",
            "down payment", "monthly payment", "finance", "musharakah", "financing",
            "home finance", "diminishing musharakah", "emi", "calculate mortgage",
            "calculate installment", "monthly kist"
        )
        if not any(k in lowered for k in mortgage_keywords):
            return None

        budget = EstateAgent._extract_budget(lowered)
        if budget is None and state.selected_property_ids:
            selected = self.properties.get_available(state.selected_property_ids[0])
            budget = selected.price_pkr if selected is not None else None
        if budget is None:
            return None

        down_match = re.search(r"(\d+)\s*(?:%|percent|prcnt)", lowered)
        if not down_match:
            down_match = re.search(r"(\d+)\s*(?:down|peshgi)", lowered)
        down_pct = int(down_match.group(1)) if down_match else 25
        down_pct = max(10, min(80, down_pct))

        tenure_match = re.search(r"(\d+)\s*(?:saal|years?|yr|yrs)", lowered)
        tenure_years = int(tenure_match.group(1)) if tenure_match else 20
        tenure_years = max(1, min(30, tenure_years))

        finance_type = "unspecified"
        if "conventional" in lowered or "sood" in lowered or "interest" in lowered:
            finance_type = "conventional"
        elif "musharakah" in lowered or "islamic" in lowered:
            finance_type = "diminishing_musharakah"

        loan_amount = budget * (1 - (down_pct / 100))
        summary = f"Opened the installment estimator for {budget:,} PKR ({down_pct}% down, {tenure_years} yrs). Confirm the editable rate in the calculator."
        return AgentAction(
            kind="calculate_mortgage",
            payload={
                "property_price_pkr": budget,
                "down_payment_pct": down_pct,
                "tenure_years": tenure_years,
                "finance_type": finance_type,
                "loan_amount_pkr": int(loan_amount),
            },
            summary=summary,
            executed=True,
        )

    @staticmethod
    def _extract_shortlist_action(text: str, state: ConversationState) -> AgentAction | None:
        lowered = text.lower()
        shortlist_keywords = (
            "shortlist", "favorite", "favourite", "save this", "save property",
            "save to shortlist", "add to shortlist", "add to favorite", "add to favorites",
            "shortlist mein", "save kar", "pasand aayi", "pasand hai", "bookmark",
            "shortlist kar", "save option", "save first", "save second", "save the first",
            "save the second", "add the first option", "add the second option"
        )
        if not any(k in lowered for k in shortlist_keywords):
            return None

        is_remove = any(w in lowered for w in ("remove", "delete", "hata", "nikal", "drop", "hatao"))
        action_type = "remove" if is_remove else "add"

        prop_id = None
        prop_match = re.search(r"\b(prop-\d+|isl-\d+|khi-\d+|lhr-\d+)\b", lowered)
        if prop_match:
            prop_id = prop_match.group(1).upper()
        elif any(w in lowered for w in ("first", "pehli", "option 1", "pehla")):
            if state.selected_property_ids:
                prop_id = state.selected_property_ids[0]
        elif any(w in lowered for w in ("second", "doosri", "option 2", "doosra")):
            if len(state.selected_property_ids) > 1:
                prop_id = state.selected_property_ids[1]
        elif state.selected_property_ids:
            prop_id = state.selected_property_ids[0]

        if not prop_id:
            return None

        summary = f"{'Saved' if action_type == 'add' else 'Removed'} {prop_id} {'to' if action_type == 'add' else 'from'} shortlist"
        return AgentAction(
            kind="shortlist_property",
            payload={
                "property_id": prop_id,
                "action": action_type,
            },
            summary=summary,
            executed=True,
        )

    @staticmethod
    def _extract_compare_action(text: str, state: ConversationState) -> AgentAction | None:
        lowered = _normalize_voice_text(text)
        compare_requested = any(
            marker in lowered
            for marker in ("compare", "comparison", "side by side", "side-by-side", "muqabla", "farq batao")
        )
        if not compare_requested:
            return None
        property_ids = state.selected_property_ids[:3]
        if len(property_ids) < 2:
            return AgentAction(
                kind="compare_properties",
                payload={"property_ids": property_ids, "needs_search": True},
                summary="A search needs at least two available listings before they can be compared.",
                executed=False,
            )
        return AgentAction(
            kind="compare_properties",
            payload={"property_ids": property_ids},
            summary=f"Opened a side-by-side comparison of {len(property_ids)} available listings.",
            executed=True,
        )

    @staticmethod
    def _extract_navigation_action(text: str) -> AgentAction | None:
        lowered = text.lower()
        nav_targets = (
            (("catalog", "properties", "listings", "all properties", "explore"), "/catalog", "Property Catalog"),
            (("calculator", "finance", "mortgage calculator", "loan calculator"), "/calculator", "Home Finance Calculator"),
            (("contact", "appointments", "book visit", "agent contact"), "/contact", "Contact & Appointments"),
            (("home", "homepage", "main page"), "/", "Home"),
        )
        is_nav = any(w in lowered for w in ("go to", "open", "show me", "take me to", "navigate to", "kholo", "dikhao", "par jao"))
        if not is_nav:
            return None

        for keywords, path, label in nav_targets:
            if any(k in lowered for k in keywords):
                return AgentAction(
                    kind="navigate_to",
                    payload={"path": path, "label": label},
                    summary=f"Navigated to {label} ({path})",
                    executed=True,
                )
        return None

    @staticmethod
    def _is_greeting(text: str) -> bool:
        tokens = set(re.findall(r"[a-z']+", text))
        return (
            bool(tokens & {"hello", "hi", "hey", "salam", "assalam", "aoa", "ao"})
            or "assalam-o-alaikum" in text
        )

    @staticmethod
    def _is_goodbye(text: str) -> bool:
        tokens = set(re.findall(r"[a-z']+", text))
        return (
            bool(tokens & {"goodbye", "bye", "allahhafiz", "khuda-hafiz", "khudahafiz"})
            or "allah hafiz" in text
            or "khuda hafiz" in text
        )

    @staticmethod
    def _unknown_request_reply(
        text: str, language: str, has_previous_dialogue: bool
    ) -> str:
        """Give a useful, language-matched recovery when no model can resolve a turn."""
        lowered = _normalize_voice_text(text)
        asks_what_we_do = any(
            phrase in lowered
            for phrase in (
                "kya kya", "aap kya karte", "aap kya kar sakte", "kya madad",
                "what all", "what can you do", "what do you do", "how can you help",
                "what can you help",
            )
        ) or any(phrase in text for phrase in ("کیا کیا", "آپ کیا", "کیا مدد"))

        if asks_what_we_do:
            if language == "ur-Arab" or any("\u0600" <= char <= "\u06ff" for char in text):
                return "میں خریدنے یا کرائے کے لیے گھر، فلیٹ، پلاٹ یا کمرشل پراپرٹی تلاش کرنے، لسٹنگ کی تفصیل بتانے اور وزٹ کی درخواست میں مدد کر سکتا ہوں۔ آپ کس شہر اور کس قسم کی پراپرٹی دیکھ رہے ہیں؟"
            if language == "ur-Latn":
                return "Main ghar, flat, plot ya commercial property buy ya rent par dhoondhne, listing details samjhane aur viewing request mein madad kar sakta hoon. Aap kis shehar mein kya dekh rahe hain?"
            return "I can help find homes, plots, apartments, or commercial spaces to buy or rent, explain listing details, and request a viewing. Which city and property type are you interested in?"

        if has_previous_dialogue:
            if language == "ur-Arab" or any("\u0600" <= char <= "\u06ff" for char in text):
                return "معذرت، آپ کا مطلب واضح نہیں ہوا۔ کیا آپ پراپرٹی تلاش کرنے، کسی لسٹنگ کی تفصیل، یا وزٹ کے بارے میں پوچھ رہے ہیں؟"
            if language == "ur-Latn":
                return "Maazrat, aap ka matlab clear nahi hua. Kya aap property search, kisi listing ki details, ya viewing ke baare mein pooch rahe hain?"
            return "I’m not sure which part you mean. Are you asking about finding a property, details on a listing, or arranging a viewing?"

        if language == "ur-Arab":
            return "میں پراپرٹی لسٹنگز، ان کی تفصیل اور وزٹ میں مدد کر سکتا ہوں۔ آپ کس چیز کے بارے میں جاننا چاہتے ہیں؟"
        if language == "ur-Latn":
            return "Main property listings, unki details aur viewing mein madad kar sakta hoon. Aap kis cheez ke baare mein jaanna chahte hain?"
        return "I can help with property listings, their details, and viewings. What would you like to know?"

    @staticmethod
    def _empty_inventory_reply(state: ConversationState) -> str:
        """Acknowledge retained preferences and ask for only the next missing detail."""

        location = ""
        if state.city and state.area:
            area = "DHA" if state.area.casefold() == "dha" else state.area.title()
            location = f"{state.city}, {area} mein "
        elif state.city:
            location = f"{state.city} mein "
        elif state.area:
            area = "DHA" if state.area.casefold() == "dha" else state.area.title()
            location = f"{area} mein "

        purpose = {
            Intent.BUY: "buy",
            Intent.RENT: "rent",
            Intent.COMMERCIAL: "commercial",
            Intent.INVEST: "investment",
        }.get(state.intent)
        if state.city and state.area and purpose:
            area = "DHA" if state.area.casefold() == "dha" else state.area.title()
            return (
                "Company listings abhi load nahi hain. "
                f"{state.city}, {area} mein {purpose} ke options verify nahi kar sakti."
            )
        preference = f"{location}{purpose} preference note kar li." if purpose else ""
        budget = f"{state.budget:,} PKR budget note kar liya." if state.budget is not None else ""
        context = " ".join(part for part in (preference, budget) if part)
        if state.city is None:
            follow_up = "Aap kis city mein options dekh rahe hain?"
        elif state.budget is None:
            follow_up = "Aapka budget range kya hai?"
        elif state.area is None:
            follow_up = "Kaunsa area prefer karte hain?"
        else:
            follow_up = "Company listings load hone ke baad exact match verify ho sakega."

        lead_in = "Verified listings abhi load nahi hain."
        return " ".join(part for part in (lead_in, context, follow_up) if part)

    def respond(self, conversation_id: str, text: str, language: str = "en") -> AgentDecision:
        result = self.graph.invoke(
            {"conversation_id": conversation_id, "text": text, "language": language}
        )
        decision = result["decision"]
        # Greeting, goodbye, guardrail, and action routes also belong to durable dialogue.
        if result.get("blocked") or result.get("route") in {"greeting", "goodbye", "execute_action"}:
            state = self._load_state(conversation_id)
            state.history.append(f"Caller: {redact_for_retention(text)}")
            self._finish(conversation_id, state, decision)
        return decision

    def _load_state(self, conversation_id: str) -> ConversationState:
        state = self.states.get(conversation_id)
        if state is None and self.state_store is not None:
            stored = self.state_store.load(conversation_id)
            if stored:
                stored["intent"] = Intent(str(stored.get("intent", Intent.UNKNOWN.value)))
                state = ConversationState(**stored)
        state = state or ConversationState()
        self.states[conversation_id] = state
        return state

    def _decide(
        self, conversation_id: str, text: str, detected_intent: Intent, language: str = "en"
    ) -> AgentDecision:
        lowered = _normalize_voice_text(text)
        state = self._load_state(conversation_id)
        state.history.append(f"Caller: {redact_for_retention(text)}")
        state.history = state.history[-20:]
        previous_dialogue = state.history[:-1]
        state.detected_language = language
        if not text.strip():
            return self._finish(conversation_id, state, AgentDecision(
                kind="ask_clarification", reason="silent_caller",
                spoken_text="Ji, main yahin hoon. Aap ki awaaz clear nahi aayi; dobara bata dein?",
            ))
        if any(marker in lowered for marker in ("angry", "furious", "terrible service", "ghussa", "bakwas", "complaint")):
            state.escalation_reason = "customer_complaint"
            return self._finish(conversation_id, state, AgentDecision(
                kind="handoff", reason="customer_complaint",
                spoken_text="Aap ki pareshani samajh sakta hoon. Kya main human consultant se baat karne ki request record karoon?",
            ))
        if any(marker in lowered for marker in ("write code", "write a poem", "weather", "cricket score", "cooking recipe", "politics")):
            return self._finish(conversation_id, state, AgentDecision(
                kind="ask_clarification", reason="off_topic",
                spoken_text="Main property inquiries aur visits mein help karta hoon. Aap ko kis city mein property chahiye?",
            ))
        advice_markers = (
            " vs ",
            " versus ",
            "farq",
            "faraq",
            "difference",
            "kahan behtar",
            "kya behtar",
            "kaunsa behtar",
            "konsa behtar",
            "guide kar",
            "mashwara",
            "advice",
            "procedure",
            "process",
            "rules",
            "tax",
            "fbr",
            "pros and cons",
            "compare",
            "comparison",
            "briefing",
            "overview",
            "market update",
            "market briefing",
            "first-time buyer",
            "first time buyer",
            "before deciding to visit",
            "what checks should i make",
            "what should i check before",
        )
        is_advice_query = any(marker in lowered for marker in advice_markers)
        if not is_advice_query:
            if detected_intent in (
                Intent.BUY,
                Intent.RENT,
                Intent.COMMERCIAL,
                Intent.INVEST,
                Intent.SELL,
            ):
                state.lead_profile["qualified_intent"] = detected_intent.value
            state.intent = detected_intent if detected_intent != Intent.UNKNOWN else state.intent
            asked_buy_or_rent = any(
                message.startswith("Agent: ")
                and "khareedna chahte hain ya rent par" in message.casefold()
                for message in previous_dialogue
            )
            answered_rent = any(
                marker in lowered
                for marker in (
                    "rent", "riend", "رینٹ", "رینت", "رنت", "رنٹ", "وینٹ", "کرایہ", "کرائے", "کرایے"
                )
            ) or "پر لینا" in lowered or "par lena" in lowered
            if state.intent == Intent.UNKNOWN and asked_buy_or_rent and answered_rent:
                state.intent = Intent.RENT
            parsed_budget = self._extract_budget(lowered)
            if parsed_budget is not None:
                state.budget = parsed_budget
            parsed_city = self._extract_city(lowered)
            if parsed_city:
                state.city = parsed_city
            parsed_area = self._extract_area(lowered)
            if parsed_area:
                state.area = parsed_area
            parsed_bedrooms = self._extract_bedrooms(lowered)
            if parsed_bedrooms is not None:
                state.bedrooms = parsed_bedrooms
            parsed_size = parse_land_size(lowered)
            if parsed_size is not None:
                state.target_size_sqft = parsed_size["size_sqft"]
                state.land_unit = parsed_size["unit"]
        known_amenities = ("parking", "security", "masjid", "pool", "gym", "generator", "rooftop")
        state.amenities = sorted(
            {*state.amenities, *(item for item in known_amenities if item in lowered)}
        )
        for goal, markers in {
            "rental yield": ("rental yield", "rent yield", "passive income"),
            "capital appreciation": ("capital appreciation", "appreciation", "price growth"),
        }.items():
            if any(marker in lowered for marker in markers):
                state.investment_goal = goal
        if state.intent == Intent.UNKNOWN and (state.budget is not None or state.target_size_sqft is not None) and state.area is not None:
            state.intent = Intent.BUY
        if state.intent == Intent.UNKNOWN and self._is_unqualified_home_request(lowered):
            location = f"{state.city} ke liye " if state.city else ""
            budget = f"{state.budget:,} PKR budget note kar liya. " if state.budget else ""
            return self._finish(
                conversation_id,
                state,
                AgentDecision(
                    kind="ask_clarification",
                    reason="property_transaction_type",
                    spoken_text=(
                        f"{budget}{location}aap ghar khareedna chahte hain ya rent par lena hai?"
                    ),
                ),
            )
        if state.selected_property_ids and any(
            marker in lowered
            for marker in ("sasta", "sasti", "cheaper", "less expensive", "kam price")
        ):
            selected = [self.properties.get_available(item) for item in state.selected_property_ids]
            prices = [item.price_pkr for item in selected if item is not None]
            if prices:
                state.budget = max(1, min(prices) - 1)
        if state.intent == Intent.SELL:
            state.escalation_reason = "seller_lead"
            return self._finish(
                conversation_id,
                state,
                AgentDecision(
                    kind="handoff",
                    reason="seller_lead",
                    spoken_text="Ji, seller request ke liye main human property consultant ko aap ki details bhej deta hoon. Please consented contact form fill kar dein.",
                ),
            )
        if state.intent in (Intent.BOOK, Intent.RESCHEDULE, Intent.CANCEL):
            state.appointment_status = "pending_confirmation"
            action = "book" if state.intent == Intent.BOOK else state.intent.value
            viewing_actions = [
                AgentAction(
                    kind="schedule_viewing",
                    payload={"property_id": state.selected_property_ids[0] if state.selected_property_ids else ""},
                    summary="Opened the viewing request form. The visit is not booked until you confirm a slot and consented contact details.",
                    executed=True,
                )
            ] if state.intent == Intent.BOOK else []
            return self._finish(
                conversation_id,
                state,
                AgentDecision(
                    kind=action,
                    spoken_text="Ji bilkul. Appointment form mein reference aur consented contact details confirm kar dein, phir main verified slot process karunga.",
                    property_ids=state.selected_property_ids[:1] if state.selected_property_ids else [],
                    actions=viewing_actions,
                ),
            )

        compare_action = self._extract_compare_action(text, state)
        if compare_action is not None:
            if not compare_action.executed:
                return self._finish(conversation_id, state, AgentDecision(
                    kind="ask_clarification",
                    spoken_text="I need at least two current listings first. Tell me a city, area, or budget and I’ll search, then compare the available options.",
                ))
            property_ids = [str(item) for item in compare_action.payload["property_ids"]]
            return self._finish(conversation_id, state, AgentDecision(
                kind="execute_action",
                spoken_text=f"I found {len(property_ids)} current options from your last search. I’ve opened them side by side so you can compare price, size, and details.",
                property_ids=property_ids,
                actions=[compare_action],
            ))

        mortgage_action = self._extract_mortgage_action(text, state)
        mortgage_markers = (
            "mortgage", "installment", "installments", "kist", "kisht", "loan",
            "down payment", "monthly payment", "finance", "musharakah", "financing",
            "home finance", "diminishing musharakah", "emi", "calculate mortgage",
            "calculate installment", "monthly kist",
        )
        if any(marker in lowered for marker in mortgage_markers) and mortgage_action is None:
            return self._finish(conversation_id, state, AgentDecision(
                kind="ask_clarification",
                spoken_text="I can open the installment estimator. Which property should I use, or what is its price in PKR? I won’t assume a price or financing rate.",
            ))
        if mortgage_action is not None:
            price = mortgage_action.payload["property_price_pkr"]
            down = mortgage_action.payload["down_payment_pct"]
            tenure = mortgage_action.payload["tenure_years"]
            if language == "ur-Arab":
                spoken = f"جی، {price:,} روپے کے پراپرٹی بجٹ، {down} فیصد ڈاؤن پیمنٹ اور {tenure} سال کے لیے قسط کا تخمینہ کیلکولیٹر میں کھول دیا ہے۔ شرح وہاں دیکھی اور تبدیل کی جا سکتی ہے۔"
            elif language == "ur-Latn":
                spoken = f"Ji, {price:,} PKR property price, {down}% down payment aur {tenure} saal ke liye installment estimate khol diya hai. Rate calculator mein dekh aur change kar sakte hain."
            else:
                spoken = f"I opened the installment estimator for a PKR {price:,} property, with {down}% down over {tenure} years. Review or change the rate in the calculator before relying on the estimate."
            return self._finish(
                conversation_id,
                state,
                AgentDecision(
                    kind="execute_action",
                    spoken_text=spoken,
                    actions=[mortgage_action],
                ),
            )

        shortlist_action = self._extract_shortlist_action(text, state)
        shortlist_markers = (
            "shortlist", "favorite", "favourite", "save this", "save property",
            "save to shortlist", "add to shortlist", "add to favorite", "add to favorites",
            "shortlist mein", "save kar", "pasand aayi", "pasand hai", "bookmark",
            "shortlist kar", "save option", "save first", "save second", "save the first",
            "save the second", "add the first option", "add the second option",
        )
        if any(marker in lowered for marker in shortlist_markers) and shortlist_action is None:
            return self._finish(conversation_id, state, AgentDecision(
                kind="ask_clarification",
                spoken_text="I need a current listing to save. Search for properties first, or tell me the property reference.",
            ))
        if shortlist_action is not None:
            is_add = shortlist_action.payload["action"] == "add"
            prop_id = shortlist_action.payload["property_id"]
            if language == "ur-Arab":
                spoken = f"جی بالکل، میں نے یہ پراپرٹی آپ کی شارٹ لسٹ میں {'محفوظ کر دی ہے' if is_add else 'سے ہٹا دی ہے'}۔"
            elif language == "ur-Latn":
                spoken = f"Ji bilkul, maine yeh property aap ki shortlist {'mein save kar di hai' if is_add else 'se remove kar di hai'}. Header mein Saved counter update ho gaya hai."
            else:
                spoken = f"Done! I have {'added this property to' if is_add else 'removed this property from'} your shortlist. Your saved listings counter has been updated."
            return self._finish(
                conversation_id,
                state,
                AgentDecision(
                    kind="execute_action",
                    spoken_text=spoken,
                    property_ids=[prop_id] if prop_id != "CURRENT_PROPERTY" else (state.selected_property_ids[:1] if state.selected_property_ids else []),
                    actions=[shortlist_action],
                ),
            )

        nav_action = self._extract_navigation_action(text)
        if nav_action is not None:
            label = nav_action.payload["label"]
            if language == "ur-Arab":
                spoken = f"جی ضرور، میں آپ کو {label} پیج پر لے چلتا ہوں۔"
            elif language == "ur-Latn":
                spoken = f"Ji zaroor, main aap ko {label} page par le chalta hoon."
            else:
                spoken = f"Certainly, navigating to {label} now."
            return self._finish(
                conversation_id,
                state,
                AgentDecision(
                    kind="execute_action",
                    spoken_text=spoken,
                    actions=[nav_action],
                ),
            )
        detail = self._property_detail_answer(state, text)
        if detail is not None:
            return self._finish(conversation_id, state, detail)
        if any(
            marker in lowered
            for marker in (
                "too expensive",
                "mehnga",
                "mehngi",
                "trust issue",
                "not sure",
                "location concern",
                "builder concern",
                "maintenance",
                "investment concern",
                "trust",
            )
        ):
            return self._finish(
                conversation_id,
                state,
                AgentDecision(
                    kind="ask_clarification",
                    spoken_text="Samajh sakta hoon. Aap ka main concern price, location, ya builder trust hai? Main sirf verified details ke basis par option compare karunga.",
                ),
            )
        # Domain Advisory Engines: Land Units, FBR Taxes, and Legal NOC
        land_conv = explain_land_conversion(text)
        if land_conv is not None:
            return self._finish(
                conversation_id,
                state,
                AgentDecision(kind="answer", spoken_text=land_conv),
            )
        tax_advisory = explain_tax_query(text, state.budget)
        if tax_advisory is not None:
            return self._finish(
                conversation_id,
                state,
                AgentDecision(kind="answer", spoken_text=tax_advisory),
            )
        legal_status = verify_legal_status(text, state.area)
        if legal_status is not None:
            return self._finish(
                conversation_id,
                state,
                AgentDecision(kind="answer", spoken_text=legal_status),
            )

        if is_advice_query:
            if any(k in lowered for k in ("yield", "yields", "roi", "rental return")):
                return self._finish(
                    conversation_id,
                    state,
                    AgentDecision(
                        kind="answer",
                        spoken_text=(
                            "I can compare rental yields once I have current, verified listing and rental data. "
                            "I don't have a live market feed configured right now, so I won't estimate yields or claim listings are verified."
                        ),
                    ),
                )
            if any(k in lowered for k in ("briefing", "overview", "market", "today")):
                return self._finish(
                    conversation_id,
                    state,
                    AgentDecision(
                        kind="answer",
                        spoken_text=(
                            "I don't have a live real-estate market feed configured, so I can't give a verified briefing for today. "
                            "I can answer general questions or search verified listings after they are imported."
                        ),
                    ),
                )
            if self.decision_provider is not None:
                prompt = general_qa_prompt(history=previous_dialogue)
                candidate = self._provider_decision(prompt, text)
                if candidate is not None and candidate.kind in ("answer", "ask_clarification") and not candidate.property_ids and not candidate.source_ids:
                    return self._finish(conversation_id, state, candidate)
            if any(
                marker in lowered
                for marker in (
                    "first-time buyer",
                    "first time buyer",
                    "before deciding to visit",
                    "what checks should i make",
                    "what should i check before",
                )
            ):
                spoken_text = (
                    "جانے سے پہلے مکمل قیمت، ادائیگی کی شرائط اور موجودہ دستیابی کمپنی کے ریکارڈ سے چیک کریں۔ "
                    "وزٹ پر اپنے سوالات کی فہرست ساتھ رکھیں۔"
                    if language == "ur-Arab"
                    else "Visit se pehle total price, payment terms, aur current availability company records se check karein. "
                    "Visit par apne questions ki list saath rakhein."
                    if language == "ur-Latn"
                    else "Before visiting, compare the full price and payment terms, confirm current availability from company records, and bring your questions for the viewing."
                )
                return self._finish(
                    conversation_id,
                    state,
                    AgentDecision(kind="answer", spoken_text=spoken_text),
                )
        if state.intent == Intent.UNKNOWN and any(
            value is not None
            for value in (
                state.budget,
                state.city,
                state.area,
                state.bedrooms,
                state.target_size_sqft,
            )
        ):
            budget = f"{state.budget:,} PKR budget note kar liya. " if state.budget is not None else ""
            location = f"{state.city} " if state.city else ""
            area = f"({state.area}) " if state.area else ""
            if state.city is None:
                follow_up = "Kis city mein property chahiye, aur buy karni hai ya rent par leni hai?"
            else:
                follow_up = "Aap buy karna chahte hain ya rent par lena?"
            return self._finish(
                conversation_id,
                state,
                AgentDecision(
                    kind="ask_clarification",
                    reason="property_qualification",
                    spoken_text=f"{budget}{location}{area}{follow_up}",
                ),
            )
        if state.intent in (Intent.BUY, Intent.RENT, Intent.COMMERCIAL, Intent.INVEST):
            purpose = {
                Intent.BUY: "sale",
                Intent.RENT: "rent",
                Intent.COMMERCIAL: "commercial",
                Intent.INVEST: "investment",
            }[state.intent]
            query = PropertyQuery(
                city=state.city,
                area=state.area,
                purpose=purpose,
                max_budget_pkr=state.budget,
                bedrooms=state.bedrooms,
                amenities=state.amenities,
                investment_goal=state.investment_goal,
                target_size_sqft=state.target_size_sqft,
            )
            sql_started = perf_counter()
            matches = [item for item in self.properties.list(query) if item.available]
            state.tool_results["property_search"] = {
                "count": len(matches),
                "property_ids": [item.id for item in matches[:10]],
                "source": "sql",
            }
            self.traces.observe("retrieval.sql_latency_ms", (perf_counter() - sql_started) * 1000)
            self.traces.increment("retrieval:sql_queries")
            if not matches:
                self.traces.increment("retrieval:sql_misses")
                if not self.properties.list():
                    return self._finish(
                        conversation_id,
                        state,
                        AgentDecision(
                            kind="ask_clarification",
                            reason="inventory_unavailable",
                            spoken_text=self._empty_inventory_reply(state),
                        ),
                    )
                if state.budget is not None:
                    no_budget_query = query.model_copy(update={"max_budget_pkr": None})
                    price_comparable = [
                        item for item in self.properties.list(no_budget_query) if item.available
                    ]
                    if price_comparable:
                        lowest_price = min(item.price_pkr for item in price_comparable)
                        if state.budget < lowest_price:
                            state.tool_results["budget_vs_listing"] = {
                                "below_list": True,
                                "budget_pkr": state.budget,
                                "lowest_matching_price_pkr": lowest_price,
                                "property_ids": [
                                    item.id
                                    for item in price_comparable
                                    if item.price_pkr == lowest_price
                                ][:3],
                            }
                            return self._finish(
                                conversation_id,
                                state,
                                AgentDecision(
                                    kind="ask_clarification",
                                    spoken_text=(
                                        f"Aapke budget mein exact verified option nahi mila. Is area mein "
                                        f"available listing {lowest_price:,} PKR se start ho rahi hai. "
                                        "Kya main area ya budget range broaden karke options dekhoon?"
                                    ),
                                ),
                            )
                if state.area and state.city:
                    broader_query = query.model_copy(update={"area": None})
                    broader_matches = [
                        item for item in self.properties.list(broader_query) if item.available
                    ]
                    if broader_matches:
                        chosen = rank_properties(broader_matches, broader_query)[:3]
                        names = ", ".join(f"{p.area}, {p.city}" for p in chosen)
                        state.selected_property_ids = [p.id for p in chosen]
                        return self._finish(
                            conversation_id,
                            state,
                            AgentDecision(
                                kind="recommend",
                                property_ids=[p.id for p in chosen],
                                spoken_text=(
                                    f"{state.area.title()} mein direct option nahi mila, lekin {state.city} mein verified available options hain: {names}. "
                                    "Aap visit schedule karna chahenge ya kisi option ki details sunna chahenge?"
                                ),
                            ),
                        )
                return self._finish(
                    conversation_id,
                    state,
                    AgentDecision(
                        kind="ask_clarification",
                        spoken_text="Acha, is criteria mein verified available option nahi mila. City, budget, ya property type thora flexible kar sakte hain?",
                    ),
                )
            chosen = rank_properties(matches, query)[:5]
            names = ", ".join(f"{p.area}, {p.city}" for p in chosen)
            sources = self.retriever.for_properties(chosen)
            rag_started = perf_counter()
            rag_context = self.retriever.context_for(text, chosen)
            self.traces.observe("retrieval.rag_latency_ms", (perf_counter() - rag_started) * 1000)
            if self.retriever.knowledge_store is None:
                self.traces.increment("retrieval:rag_disabled")
                state.tool_results["rag_search"] = {"status": "disabled", "source_ids": []}
            else:
                self.traces.increment(
                    "retrieval:rag_hits" if rag_context else "retrieval:rag_misses"
                )
                state.tool_results["rag_search"] = {
                    "status": "hit" if rag_context else "miss",
                    "source_ids": [item.source_id for item in rag_context][:5],
                }
            state.selected_property_ids = [p.id for p in chosen]
            source_ids = [source.source_id for source in sources] + [
                source.source_id for source in rag_context
            ]
            state.retrieved_sources = source_ids[:5]
            fallback = AgentDecision(
                kind="recommend",
                property_ids=[p.id for p in chosen],
                source_ids=source_ids[:5],
                spoken_text=f"Ji bilkul. Verified available options hain: {names}. Aap visit book karna chahenge ya kisi ek option ki details sunna chahenge?",
                actions=[
                    AgentAction(
                        kind="filter_catalog",
                        payload={
                            "city": state.city,
                            "area": state.area,
                            "max_price": state.budget,
                            "bedrooms": state.bedrooms,
                            "purpose": purpose,
                            "count": len(matches),
                        },
                        summary=f"Filtered catalog: {len(matches)} listings matched in {state.city or 'all cities'}",
                        executed=True,
                    )
                ],
            )
            return self._finish(
                conversation_id,
                state,
                self._model_recommendation(text, fallback, chosen, rag_context, previous_dialogue),
            )
        if self.decision_provider is not None and len(text.strip()) > 3:
            prompt = general_qa_prompt(history=previous_dialogue)
            candidate = self._provider_decision(prompt, text)
            if candidate is not None and candidate.kind in ("answer", "ask_clarification") and not candidate.property_ids and not candidate.source_ids:
                return self._finish(conversation_id, state, candidate)
        return self._finish(
            conversation_id,
            state,
            AgentDecision(
                kind="ask_clarification",
                spoken_text=self._unknown_request_reply(
                    text, language, bool(previous_dialogue)
                ),
            ),
        )

    def _finish(
        self, conversation_id: str, state: ConversationState, decision: AgentDecision
    ) -> AgentDecision:
        lead_eval = score_lead(
            budget_pkr=state.budget,
            intent=state.intent.value,
            booked_visit=state.appointment_status is not None,
            history=[
                turn.removeprefix("Caller: ")
                for turn in state.history
                if not turn.startswith("Agent: ")
            ],
        )
        state.lead_profile["temperature"] = lead_eval["temperature"]
        state.lead_profile["score"] = str(lead_eval["score"])
        state.lead_profile["recommended_action"] = lead_eval["recommended_action"]
        state.history.append(f"Agent: {redact_for_retention(decision.spoken_text)}")
        state.history = state.history[-20:]
        if self.state_store is not None:
            self.state_store.save(conversation_id, state)
        return decision

    def _resolve_property_id(self, state: ConversationState, lowered: str) -> str | None:
        ids = re.findall(r"\b[a-zA-Z]{2,}-\d{2,}\b", lowered)
        if ids:
            return ids[0].upper()
        if state.selected_property_ids:
            ordinal_patterns = [
                (0, r"\b(first|pehla|pehli|pahla|pahli|one|1|opt(?:ion)?\s*1)\b"),
                (1, r"\b(second|doosra|doosri|dosra|dusra|two|2|opt(?:ion)?\s*2)\b"),
                (2, r"\b(third|teesra|teesri|tisra|three|3|opt(?:ion)?\s*3)\b"),
            ]
            for idx, pattern in ordinal_patterns:
                if re.search(pattern, lowered) and idx < len(state.selected_property_ids):
                    return state.selected_property_ids[idx]
            for prop_id in state.selected_property_ids:
                p = self.properties.get_available(prop_id)
                if p and (p.area.lower() in lowered or p.title.lower() in lowered):
                    return prop_id
            if len(state.selected_property_ids) == 1:
                return state.selected_property_ids[0]
        area_matches = [p.id for p in self.properties.list() if p.available and p.area.lower() in lowered]
        return area_matches[0] if len(area_matches) == 1 else None

    def _property_detail_answer(self, state: ConversationState, text: str) -> AgentDecision | None:
        """Answer only deterministic facts for an explicitly selected property."""
        lowered = text.lower()
        detail_words = (
            "price",
            "cost",
            "payment",
            "installment",
            "size",
            "sqft",
            "bedroom",
            "amenit",
            "developer",
            "facility",
            "school",
            "hospital",
            "kitne",
            "plan",
            "detail",
            "details",
            "batao",
            "bataen",
            "bataiye",
            "kaisa",
            "kaisi",
            "feature",
            "nearby",
            "tell me about",
            "kya hai",
            "info",
            "information",
        )
        is_detail_query = any(word in lowered for word in detail_words)
        selected = self._resolve_property_id(state, lowered)
        if not selected:
            if not is_detail_query or not state.selected_property_ids:
                return None
            if len(state.selected_property_ids) > 1:
                return AgentDecision(kind="ask_clarification", spoken_text="Kis option ki details chahiye: pehla, doosra, ya property reference bata dein?")
            selected = state.selected_property_ids[0]
        elif not is_detail_query and not re.search(
            r"\b(pehla|doosra|teesra|first|second|third)\b", lowered
        ):
            return None

        property_item = self.properties.get_available(selected)
        if property_item is None:
            return AgentDecision(
                kind="ask_clarification",
                spoken_text="Yeh property ab verified available nahi hai. Main fresh available options check kar doon?",
            )
        source = self.retriever.for_properties([property_item])[0]
        rag_started = perf_counter()
        rag_context = self.retriever.context_for(text, [property_item])
        self.traces.observe("retrieval.rag_latency_ms", (perf_counter() - rag_started) * 1000)
        source_ids = [source.source_id, *(item.source_id for item in rag_context)]
        nearby = ""
        if "school" in lowered:
            nearby += f" Nearby schools: {', '.join(property_item.nearby_schools) or 'not listed in the verified source'}."
        if "hospital" in lowered:
            nearby += f" Nearby hospitals: {', '.join(property_item.nearby_hospitals) or 'not listed in the verified source'}."
        fallback = AgentDecision(
            kind="answer",
            property_ids=[property_item.id],
            source_ids=source_ids[:5],
            spoken_text=(
                f"{property_item.title}, {property_item.area}, {property_item.city}. "
                f"Price PKR {property_item.price_pkr:,}, size {property_item.size_sqft} square feet, "
                f"{property_item.bedrooms} bedrooms. Payment plan: {property_item.payment_plan}. "
                f"Amenities: {', '.join(property_item.amenities)}.{nearby}"
            ),
        )
        return self._model_answer(text, fallback, property_item, rag_context, state.history[:-1])

    def _provider_decision(self, prompt: str, text: str) -> AgentDecision | None:
        if self.decision_provider is None:
            return None
        try:
            return self.decision_provider.decide(prompt, text)
        except LLMDecisionError:
            self.traces.increment("llm:failures")
            return None

    def _model_answer(
        self,
        text: str,
        fallback: AgentDecision,
        property_item: object,
        rag_context: list[object],
        history: list[str] | None = None,
    ) -> AgentDecision:
        """Allow an LLM to phrase an answer only inside the SQL/RAG source boundary."""
        if self.decision_provider is None or not rag_context:
            return fallback
        allowed_property_id = str(property_item.id)
        prompt = answer_prompt(
            allowed_property_id,
            fallback.source_ids,
            [self.retriever.for_properties([property_item])[0].text, *[getattr(item, "text", "") for item in rag_context]],
            history=history,
        )
        candidate = self._provider_decision(prompt, text)
        if candidate is None or candidate.kind != "answer":
            return fallback
        if candidate.property_ids and any(
            item != allowed_property_id for item in candidate.property_ids
        ):
            return fallback
        if not candidate.source_ids or any(item not in fallback.source_ids for item in candidate.source_ids):
            return fallback
        source_ids = candidate.source_ids
        return candidate.model_copy(
            update={
                "property_ids": [allowed_property_id],
                "source_ids": source_ids or fallback.source_ids,
                "actions": candidate.actions or fallback.actions,
            }
        )

    def _model_recommendation(
        self,
        text: str,
        fallback: AgentDecision,
        properties: list[object],
        rag_context: list[object] | None = None,
        history: list[str] | None = None,
    ) -> AgentDecision:
        if self.decision_provider is None:
            return fallback
        allowed_ids = {str(item.id) for item in properties}
        prompt = recommendation_prompt(
            sorted(allowed_ids),
            fallback.source_ids,
            [*[item.text for item in self.retriever.for_properties(properties)], *[getattr(item, "text", "") for item in (rag_context or [])]],
            history=history,
        )
        candidate = self._provider_decision(prompt, text)
        if candidate is None or candidate.kind != "recommend":
            return fallback
        if any(item not in allowed_ids for item in candidate.property_ids):
            return fallback
        property_ids = candidate.property_ids
        if not property_ids:
            return fallback
        if not candidate.source_ids or any(item not in fallback.source_ids for item in candidate.source_ids):
            return fallback
        source_ids = candidate.source_ids
        return candidate.model_copy(
            update={
                "property_ids": property_ids[: len(properties)],
                "source_ids": source_ids or fallback.source_ids,
                "actions": candidate.actions or fallback.actions,
            }
        )
