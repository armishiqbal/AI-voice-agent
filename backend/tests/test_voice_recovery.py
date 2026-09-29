import pytest

from app.services.voice_recovery import (
    telephony_provider_failure_prompt,
    transcription_recovery_prompt,
)


@pytest.mark.parametrize("language", ["ur-Latn", "ur-Arab", "en", "hi", "ar", "pa", "bn"])
def test_transcription_recovery_prompt_is_available_for_supported_languages(language: str) -> None:
    prompt = transcription_recovery_prompt(language)
    assert prompt
    assert len(prompt) <= 120


def test_transcription_recovery_does_not_guess_for_unsupported_language() -> None:
    assert transcription_recovery_prompt("xx") is None


@pytest.mark.parametrize("language", ["ur-Latn", "ur-Arab", "en"])
def test_telephony_provider_failure_prompt_is_truthful_and_localized(language: str) -> None:
    prompt = telephony_provider_failure_prompt(language)
    assert prompt
    assert len(prompt) < 140
    assert "call" in prompt.casefold() or "کال" in prompt
