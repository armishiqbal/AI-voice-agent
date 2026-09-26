from __future__ import annotations

from app.domain.emotions import (
    AUTHORITATIVE_PROFILE,
    EMPATHETIC_PROFILE,
    ENTHUSIASTIC_PROFILE,
    PROFESSIONAL_PROFILE,
    infer_acoustic_emotion,
)


def test_infer_acoustic_emotion_empathetic():
    # Budget hesitation
    profile = infer_acoustic_emotion("Yeh price bohot mehnga hai, mera budget kam hai", "answer")
    assert profile == EMPATHETIC_PROFILE
    assert profile.emotion == "empathetic"
    assert profile.speech_rate == 0.95
    assert profile.fish_audio_tag == "[empathetic]"

    # Cancellation
    profile_cancel = infer_acoustic_emotion("Visit cancel kar dein", "cancel", intent="cancel")
    assert profile_cancel == EMPATHETIC_PROFILE


def test_infer_acoustic_emotion_authoritative():
    # Legal / Tax questions
    profile = infer_acoustic_emotion("Kya is property ka SBCA NOC aur FBR 236K clear hai?", "answer")
    assert profile == AUTHORITATIVE_PROFILE
    assert profile.emotion == "authoritative"
    assert profile.speech_rate == 1.0
    assert profile.fish_audio_tag == "[serious]"


def test_infer_acoustic_emotion_enthusiastic():
    # Recommendations
    profile = infer_acoustic_emotion("Mujhe DHA Phase 6 mein luxury villa dikhayein", "recommend")
    assert profile == ENTHUSIASTIC_PROFILE
    assert profile.emotion == "enthusiastic"
    assert profile.speech_rate == 1.05
    assert profile.fish_audio_tag == "[enthusiastic]"


def test_infer_acoustic_emotion_professional_default():
    # Standard greeting or clarification
    profile = infer_acoustic_emotion("Assalam-o-Alaikum, mujhe timing bata dein", "ask_clarification")
    assert profile == PROFESSIONAL_PROFILE
    assert profile.emotion == "professional"
    assert profile.fish_audio_tag == "[calm]"
