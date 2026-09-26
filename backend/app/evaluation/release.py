from __future__ import annotations

import asyncio
from pathlib import Path

from app.agents.graph import EstateAgent
from app.core.config import Settings
from app.evaluation.appointments import run_appointment_evaluation
from app.evaluation.conversations import load_conversation_cases, run_conversation_evaluation
from app.evaluation.memory import load_memory_cases, run_memory_evaluation
from app.evaluation.rag import load_rag_cases, run_sql_baseline
from app.evaluation.runner import load_cases, run_evaluation
from app.integrations.providers import all_tts_languages_ready, provider_readiness
from app.integrations.stt import build_openai_realtime_stt
from app.integrations.tts import build_openai_tts_router, build_tts_router
from app.services.appointments import PropertyRepository


def build_release_report(root: Path, config: Settings) -> dict[str, object]:
    """Return an evidence-scoped report with live provider readiness probes."""
    repository = PropertyRepository()
    safety = run_evaluation(
        lambda: EstateAgent(repository),
        load_cases(root / "evals" / "conversations.json"),
    ).as_dict()
    retrieval = run_sql_baseline(
        repository,
        load_rag_cases(root / "evals" / "rag_questions.json"),
    )
    memory = run_memory_evaluation(
        lambda: EstateAgent(repository),
        load_memory_cases(root / "evals" / "memory.json"),
    )
    appointments = run_appointment_evaluation()
    conversations = run_conversation_evaluation(load_conversation_cases(root / "evals" / "multiturn_conversations.json"))
    readiness = provider_readiness(config)
    tts_ready = readiness.multilingual_tts and asyncio.run(
        all_tts_languages_ready(build_tts_router(config))
    )
    async def openai_audio_ready() -> bool:
        routes = await build_openai_tts_router(config).readiness()
        return readiness.openai and await build_openai_realtime_stt(config).is_ready() and routes.get("*", False)

    openai_ready = asyncio.run(openai_audio_ready())
    standard_ready = readiness.deepgram and readiness.openai and tts_ready
    providers = {
        **readiness.__dict__,
        "multilingual_tts": tts_ready,
        "standard_voice_ready": standard_ready,
        "openai_voice_ready": openai_ready,
        "live_voice_pipeline_ready": standard_ready or openai_ready,
    }
    live_voice_ready = bool(providers["live_voice_pipeline_ready"])
    return {
        "scope": "local-implementation-with-live-prerequisite-status",
        "evidence_limits": ["Fixture evaluations do not prove real company grounding", "Provider readiness does not prove a completed voice turn", "Hallucination baseline measures unexpected property IDs, not every prose claim"],
        "gates": {
            "safety": {
                "status": "passed locally"
                if safety["prompt_injection_bypasses"] == 0
                else "failed locally",
                "prompt_injection_bypasses": safety["prompt_injection_bypasses"],
            },
            "grounded_answer_rate": {
                "status": "passed locally"
                if safety["grounded_answer_rate"] >= 0.95
                else "failed locally",
                "value": safety["grounded_answer_rate"],
            },
            "retrieval_accuracy": {
                "status": "passed locally" if retrieval["accuracy"] >= 0.85 else "failed locally",
                "value": retrieval["accuracy"],
                "pinecone_evidence": retrieval["pinecone_evidence"],
            },
            "hallucination_rate": {
                "status": "passed locally"
                if retrieval["hallucination_rate"] <= 0.05
                else "failed locally",
                "value": retrieval["hallucination_rate"],
            },
            "memory_accuracy": {
                "status": "passed locally" if memory["accuracy"] >= 0.85 else "failed locally",
                "value": memory["accuracy"],
            },
            "appointment_correctness": {
                "status": "passed locally" if appointments["accuracy"] == 1.0 else "failed locally",
                "value": appointments["accuracy"],
            },
            "live_voice_latency": {
                "status": "blocked by prerequisite"
                if not live_voice_ready
                else "requires live measurement",
                "provider_readiness": live_voice_ready,
            },
            "google_delivery": {
                "status": "requires live delivery test"
                if providers["calendar"] and providers["gmail"]
                else "blocked by prerequisite",
                "configuration_ready": providers["calendar"] and providers["gmail"],
                "calendar": providers["calendar"],
                "gmail": providers["gmail"],
            },
            "telephony": {
                "status": "requires live measurement"
                if providers["telephony"]
                else "blocked by prerequisite",
                "provider_readiness": providers["telephony"],
            },
        },
        "provider_readiness": providers,
        "multiturn_conversations": conversations,
        "fixture_evaluation": safety,
        "sql_retrieval_baseline": retrieval,
        "memory_evaluation": memory,
        "appointment_evaluation": appointments,
    }
