from __future__ import annotations

import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Protocol

from app.domain.models import AgentDecision


class LLMDecisionError(RuntimeError):
    """Expected structured-model failure; callers must use deterministic fallback."""


class StructuredDecisionProvider(Protocol):
    def decide(self, system_prompt: str, user_text: str) -> AgentDecision: ...


class OpenAIStructuredDecisionProvider:
    """Optional OpenAI adapter that can only return the validated decision schema."""

    FAILURE_COOLDOWN_SECONDS = 30.0

    def __init__(self, api_key: str, model: str, timeout_seconds: float = 1.5) -> None:
        try:
            from openai import OpenAI
        except ImportError as error:
            raise LLMDecisionError(
                "Install the providers extra to enable the OpenAI adapter"
            ) from error
        # A structured decision is on the voice response path. One bounded
        # attempt is preferable to SDK retries delaying a deterministic fallback.
        self.client = OpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=0)
        self.model = model
        self.timeout_seconds = timeout_seconds
        self._retry_after = 0.0
        self._last_failure_category: str | None = None
        self._request_lock = threading.Lock()
        self._request_future: Future[AgentDecision] | None = None
        self._request_executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="structured-decision",
        )

    @property
    def failure_cooldown_remaining(self) -> float:
        """Seconds until another model attempt is allowed after a provider failure."""
        with self._request_lock:
            return max(0.0, self._retry_after - time.monotonic())

    @property
    def last_failure_category(self) -> str | None:
        """Sanitized reason for the most recent failed model request."""
        with self._request_lock:
            return getattr(self, "_last_failure_category", None)

    @classmethod
    def _failure_cooldown_seconds(cls, error: Exception) -> float:
        """Honor a provider Retry-After hint without allowing unbounded backoff."""
        if cls._failure_category(error) != "rate_limited":
            return cls.FAILURE_COOLDOWN_SECONDS

        response = getattr(error, "response", None)
        headers = getattr(response, "headers", None)
        if headers is None:
            return cls.FAILURE_COOLDOWN_SECONDS

        retry_after_ms = headers.get("retry-after-ms")
        if retry_after_ms is not None:
            try:
                delay = float(retry_after_ms) / 1000
            except (TypeError, ValueError):
                delay = 0
            if delay > 0:
                return min(300.0, max(1.0, delay))

        retry_after = headers.get("retry-after")
        if retry_after is None:
            return cls.FAILURE_COOLDOWN_SECONDS
        try:
            delay = float(retry_after)
        except (TypeError, ValueError):
            try:
                retry_at = parsedate_to_datetime(str(retry_after))
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=UTC)
                delay = (retry_at - datetime.now(UTC)).total_seconds()
            except (TypeError, ValueError, OverflowError):
                return cls.FAILURE_COOLDOWN_SECONDS
        return min(300.0, max(1.0, delay))

    def _record_late_request_result(self, future: Future[AgentDecision]) -> None:
        """Refresh sanitized status if the provider finishes after the caller deadline."""
        try:
            future.result()
        except Exception as error:  # noqa: BLE001 - provider error details stay internal
            category = self._failure_category(error)
            cooldown = self._failure_cooldown_seconds(error)
        else:
            # A late success cannot be used for the already-finished turn.
            category = "timeout"
            cooldown = self.FAILURE_COOLDOWN_SECONDS
        with self._request_lock:
            if self._request_future is not future:
                return
            self._retry_after = time.monotonic() + cooldown
            self._last_failure_category = category

    def decide(self, system_prompt: str, user_text: str) -> AgentDecision:
        with self._request_lock:
            if time.monotonic() < self._retry_after:
                raise LLMDecisionError(
                    "Structured decision provider is in a short failure cooldown"
                )
            if self._request_future is not None and not self._request_future.done():
                self._retry_after = time.monotonic() + self.FAILURE_COOLDOWN_SECONDS
                raise LLMDecisionError(
                    "A previous structured decision request is still finishing"
                )
            future = self._request_executor.submit(
                self._decide_request,
                system_prompt,
                user_text,
            )
            self._request_future = future

        try:
            decision = future.result(timeout=self.timeout_seconds)
        except FutureTimeoutError as error:
            with self._request_lock:
                self._retry_after = time.monotonic() + self.FAILURE_COOLDOWN_SECONDS
                self._last_failure_category = "timeout"
            future.add_done_callback(self._record_late_request_result)
            raise LLMDecisionError(
                "Structured decision request exceeded its wall-clock deadline"
            ) from error
        except LLMDecisionError:
            with self._request_lock:
                self._retry_after = time.monotonic() + self.FAILURE_COOLDOWN_SECONDS
                self._last_failure_category = "invalid_response"
            raise
        except Exception as error:
            with self._request_lock:
                self._retry_after = time.monotonic() + self._failure_cooldown_seconds(error)
                self._last_failure_category = self._failure_category(error)
            raise LLMDecisionError(f"Structured model request failed: {error}") from error
        with self._request_lock:
            if self._request_future is future:
                self._request_future = None
            self._retry_after = 0.0
            self._last_failure_category = None
        return decision

    @staticmethod
    def _failure_category(error: Exception) -> str:
        status_code = getattr(error, "status_code", None)
        if status_code == 429 or type(error).__name__ == "RateLimitError":
            return "rate_limited"
        if status_code in {401, 403} or type(error).__name__ == "AuthenticationError":
            return "authentication_failed"
        if isinstance(error, (TimeoutError, FutureTimeoutError)) or "timeout" in type(error).__name__.lower():
            return "timeout"
        return "provider_error"

    def _decide_request(self, system_prompt: str, user_text: str) -> AgentDecision:
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
            timeout_seconds=float(getattr(config, "llm_decision_timeout_seconds", 1.5)),
        )
    except LLMDecisionError:
        return None
