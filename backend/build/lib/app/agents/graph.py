from __future__ import annotations

import re
from dataclasses import dataclass, field
from time import perf_counter
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.prompts import answer_prompt, general_qa_prompt, recommendation_prompt
from app.core.observability import TraceStore
from app.domain.legal import verify_legal_status
from app.domain.models import AgentDecision, Intent, PropertyQuery
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
        ):
            builder.add_node(route_name, self._route_node)
        builder.add_edge(START, "guardrails")
        builder.add_conditional_edges(
            "guardrails",
            lambda state: "handoff" if state["blocked"] else "intent_detection",
            {"handoff": "handoff", "intent_detection": "intent_detection"},
        )
        builder.add_edge("intent_detection", "grounded_resolution")
        builder.add_conditional_edges(
            "grounded_resolution",
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

    def _route_node(self, graph_state: GraphState) -> dict[str, object]:
        """Explicit action nodes keep consequential routes visible in LangGraph traces."""
        route = graph_state.get("route")
        if route:
            self.traces.record(graph_state["conversation_id"], str(route), perf_counter())
        return {"decision": graph_state["decision"]}

    @staticmethod
    def _intent(text: str) -> Intent:
        value = text.lower()
        if any(word in value for word in ("cancel", "radd", "cancel kar", "mansookh", "nahi chahiye visit")):
            return Intent.CANCEL
        if any(word in value for word in ("reschedule", "change time", "time change", "waqt badalna", "doosra time")):
            return Intent.RESCHEDULE
        if any(word in value for word in ("book", "visit", "appointment", "booking", "dekhna", "dekhne jana", "visit karna", "ayesha ke saath")):
            return Intent.BOOK
        if any(word in value for word in ("sell", "bech", "bechna", "listing", "list karni")):
            return Intent.SELL
        if any(word in value for word in ("rent", "kiraya", "kiraye", "kiraaye", "rental", "rent pe", "rent par", "rent ka", "monthly rent")):
            return Intent.RENT
        if any(word in value for word in ("commercial", "office", "shop", "dukan", "dukaan", "plaza", "warehouse", "godam")):
            return Intent.COMMERCIAL
        if any(word in value for word in ("invest", "investment", "roi", "passive income", "yield", "sarmayakari", "munafa")):
            return Intent.INVEST
        if any(word in value for word in ("buy", "kharid", "khareed", "purchase", "plot", "flat", "flats", "house", "houses", "makan", "makaan", "kothi", "bangla", "villa", "villas", "bungalow", "apartment", "apartments", "zameen", "file")):
            return Intent.BUY
        return Intent.UNKNOWN

    @staticmethod
    def _extract_budget(lowered: str) -> int | None:
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

        crore_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:crore|cr)\b", lowered)
        if crore_match:
            return int(float(crore_match.group(1)) * 10_000_000)

        lakh_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:lakh|lac|lacs)\b", lowered)
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
        cities = (
            "karachi", "lahore", "islamabad", "rawalpindi", "faisalabad",
            "multan", "peshawar", "quetta", "gwadar", "hyderabad", "sialkot",
            "gujranwala", "abbottabad", "bahawalpur", "sargodha"
        )
        for city in cities:
            if re.search(rf"\b{city}\b", lowered):
                return city.title()
        return None

    @staticmethod
    def _extract_area(lowered: str) -> str | None:
        areas = (
            "dha phase 6", "dha phase 5", "dha phase 2", "dha",
            "clifton", "gulberg", "f-11", "bahria town", "bahria enclave", "bahria orchard", "bahria",
            "blue area", "gulshan-e-iqbal", "gulshan", "pechs", "cantt", "johar town", "johar",
            "model town", "e-11", "g-11", "f-7", "f-8", "f-10", "i-8", "askari", "wapda town"
        )
        for area in areas:
            if area in lowered:
                return area
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

    def respond(self, conversation_id: str, text: str, language: str = "en") -> AgentDecision:
        result = self.graph.invoke(
            {"conversation_id": conversation_id, "text": text, "language": language}
        )
        decision = result["decision"]
        # Greeting, goodbye and guardrail routes also belong to durable dialogue.
        if result.get("blocked") or result.get("route") in {"greeting", "goodbye"}:
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
        lowered = text.lower()
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
            return self._finish(
                conversation_id,
                state,
                AgentDecision(
                    kind=action,
                    spoken_text="Ji bilkul. Appointment form mein reference aur consented contact details confirm kar dein, phir main verified slot process karunga.",
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
                spoken_text="Assalam-o-Alaikum. Main verified property options aur visits mein help karta hoon. Aap buy, rent, commercial, ya investment ke liye dekh rahe hain?",
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
            }
        )
