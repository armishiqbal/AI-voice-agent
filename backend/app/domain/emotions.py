from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AcousticEmotion = Literal["enthusiastic", "empathetic", "authoritative", "professional"]


@dataclass(frozen=True)
class AcousticEmotionProfile:
    """Acoustic modulation profile for neural speech synthesis."""

    emotion: AcousticEmotion
    speech_rate: float
    pitch_offset: float
    fish_audio_tag: str
    prompt_guidance: str
    description: str

    def as_dict(self) -> dict[str, object]:
        return {
            "emotion": self.emotion,
            "speech_rate": self.speech_rate,
            "pitch_offset": self.pitch_offset,
            "fish_audio_tag": self.fish_audio_tag,
            "prompt_guidance": self.prompt_guidance,
            "description": self.description,
        }


ENTHUSIASTIC_PROFILE = AcousticEmotionProfile(
    emotion="enthusiastic",
    speech_rate=1.05,
    pitch_offset=1.0,
    fish_audio_tag="[enthusiastic]",
    prompt_guidance=(
        "Speak with genuine warmth, energy, and enthusiasm. "
        "Highlight the property highlights with bright, uplifting Pakistani sales cadence."
    ),
    description="Upbeat, engaging tone for property recommendations and investment opportunities.",
)

EMPATHETIC_PROFILE = AcousticEmotionProfile(
    emotion="empathetic",
    speech_rate=0.95,
    pitch_offset=-0.5,
    fish_audio_tag="[empathetic]",
    prompt_guidance=(
        "Speak with deep empathy, gentle patience, and reassurance. "
        "Use a comforting, unhurried pace to address caller hesitations, budget worries, or cancellations."
    ),
    description="Gentle, reassuring tone for budget constraints, objections, or cancellations.",
)

AUTHORITATIVE_PROFILE = AcousticEmotionProfile(
    emotion="authoritative",
    speech_rate=1.0,
    pitch_offset=0.0,
    fish_audio_tag="[serious]",
    prompt_guidance=(
        "Speak with steady, crisp authority and confidence. "
        "Articulate legal approvals, FBR tax sections, and regulatory compliances clearly and decisively."
    ),
    description="Crisp, authoritative tone for legal verification, tax calculations, and official approvals.",
)

PROFESSIONAL_PROFILE = AcousticEmotionProfile(
    emotion="professional",
    speech_rate=1.0,
    pitch_offset=0.0,
    fish_audio_tag="[calm]",
    prompt_guidance=(
        "Speak with courteous, professional Pakistani real estate consultant hospitality. "
        "Maintain clear, balanced, and respectful UrduLish conversational flow."
    ),
    description="Standard courteous, balanced tone for greetings, scheduling, and general inquiries.",
)


EMPATHETIC_KEYWORDS = frozenset(
    {
        "expensive",
        "mehnga",
        "ziada",
        "zyada",
        "budget kam",
        "afford",
        "kam budget",
        "dar",
        "fraud",
        "scam",
        "cancel",
        "mansookh",
        "radd",
        "masla",
        "tension",
        "problem",
        "loss",
        "issue",
    }
)

AUTHORITATIVE_KEYWORDS = frozenset(
    {
        "legal",
        "tax",
        "fbr",
        "236k",
        "236c",
        "7e",
        "sbca",
        "cda",
        "lda",
        "rda",
        "kda",
        "fda",
        "noc",
        "fard",
        "intiqal",
        "registry",
        "shajra",
        "approval",
        "approved",
        "authority",
        "dispute",
        "clearance",
    }
)

ENTHUSIASTIC_KEYWORDS = frozenset(
    {
        "bohat acha",
        "prime",
        "luxury",
        "shandar",
        "penthouse",
        "zabardast",
        "roi",
        "passive income",
        "dream home",
        "exclusive",
        "bohot khoob",
    }
)


def infer_acoustic_emotion(
    text: str,
    decision_kind: str,
    intent: str | None = None,
    response_text: str | None = None,
) -> AcousticEmotionProfile:
    """Determine the optimal acoustic emotion profile based on conversational signals."""
    combined = f"{text} {response_text or ''}".lower()

    # 1. Empathetic / Reassuring check
    if decision_kind == "cancel" or intent == "cancel":
        return EMPATHETIC_PROFILE
    if any(keyword in combined for keyword in EMPATHETIC_KEYWORDS):
        return EMPATHETIC_PROFILE

    # 2. Authoritative check
    if any(keyword in combined for keyword in AUTHORITATIVE_KEYWORDS):
        return AUTHORITATIVE_PROFILE

    # 3. Enthusiastic check
    if (decision_kind == "recommend" or intent in ("invest", "buy")) and (
        any(keyword in combined for keyword in ENTHUSIASTIC_KEYWORDS) or decision_kind == "recommend"
    ):
        return ENTHUSIASTIC_PROFILE

    # 4. Professional default
    return PROFESSIONAL_PROFILE
