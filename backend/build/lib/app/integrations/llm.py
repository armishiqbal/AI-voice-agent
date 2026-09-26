from __future__ import annotations

from typing import Protocol

from app.domain.models import AgentDecision


class LLMDecisionError(RuntimeError):
    """Expected structured-model failure; callers must use deterministic fallback."""


class StructuredDecisionProvider(Protocol):
    def decide(self, system_prompt: str, user_text: str) -> AgentDecision: ...


class OpenAIStructuredDecisionProvider:
    """Optional OpenAI adapter that can only return the validated decision schema."""

    def __init__(self, api_key: str, model: str, timeout_seconds: float = 20.0) -> None:
        try:
            from openai import OpenAI
        except ImportError as error:
            raise LLMDecisionError(
                "Install the providers extra to enable the OpenAI adapter"
            ) from error
        self.client = OpenAI(api_key=api_key, timeout=timeout_seconds)
        self.model = model

    def decide(self, system_prompt: str, user_text: str) -> AgentDecision:
        try:
            response = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text},
                ],
                response_format=AgentDecision,
            )
            message = response.choices[0].message
            if message.refusal or message.parsed is None:
                raise LLMDecisionError("The model refused or returned no structured decision")
            return message.parsed
        except LLMDecisionError:
            raise
        except Exception as error:
            raise LLMDecisionError(f"Structured model request failed: {error}") from error


class OpenAIEmbeddingProvider:
    """Synchronous embedding adapter used by the ingestion and query paths."""

    def __init__(
        self, api_key: str, model: str = "text-embedding-3-small", timeout_seconds: float = 20.0
    ) -> None:
        try:
            from openai import OpenAI
        except ImportError as error:
            raise LLMDecisionError(
                "Install the providers extra to enable OpenAI embeddings"
            ) from error
        self.client = OpenAI(api_key=api_key, timeout=timeout_seconds)
        self.model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            response = self.client.embeddings.create(model=self.model, input=texts)
            return [item.embedding for item in sorted(response.data, key=lambda item: item.index)]
        except Exception as error:
            raise LLMDecisionError(f"Embedding request failed: {error}") from error


def build_decision_provider(config: object) -> StructuredDecisionProvider | None:
    """Return None when credentials are absent; never invent a provider response."""

    provider = getattr(config, "llm_provider", "openai")
    api_key = getattr(config, "openai_api_key", None)
    if provider != "openai" or not api_key:
        return None
    try:
        return OpenAIStructuredDecisionProvider(
            api_key=api_key,
            model=getattr(config, "llm_model", "gpt-4o-mini"),
            timeout_seconds=float(getattr(config, "llm_timeout_seconds", 20.0)),
        )
    except LLMDecisionError:
        return None
