import test from "node:test";
import assert from "node:assert/strict";
import {
  resolveDisplayedVoicePhase,
  resolveAudioUnavailableMessage,
  resolveSttUnavailableMessage,
  resolveVoiceNotReadyMessage,
  resolveVoiceConnectionStatus,
  parseRuntimeReadiness,
  parseStructuredReasoningStatus,
  shouldApplyServerVoicePhase,
  shouldOfferVoiceRetry,
} from "../src/voiceUiState.mjs";

test("reasoning status from text turns and voice events is validated and sanitized", () => {
  assert.deepEqual(parseStructuredReasoningStatus({
    reasoning_status: "provider_error",
    reasoning_failure_category: "rate_limited",
    raw_error: "must not surface",
  }), { status: "provider_error", failureCategory: "rate_limited" });
  assert.deepEqual(parseStructuredReasoningStatus({
    status: "cooldown",
    last_failure_category: "timeout",
    api_key: "must not surface",
  }), { status: "cooldown", failureCategory: "timeout" });
  assert.equal(parseStructuredReasoningStatus({ status: "healthy", failure_category: "other" }), null);
});

test("runtime readiness exposes only validated provider, route, and blocker details", () => {
  assert.deepEqual(parseRuntimeReadiness({
    status: "degraded",
    mode: "blocked",
    structured_reasoning: { status: "cooldown", fallback: "deterministic", last_failure_category: "rate_limited" },
    providers: { hybrid_voice_ready: false, debug: "ignore" },
    live_voice: {
      verification: "configuration_only",
      options: { hybrid: false, malformed: 1 },
      blockers: ["Deepgram streaming STT", 5, " OpenAI structured agent "],
    },
  }), {
    ready: false,
    mode: "blocked",
    voiceVerification: "configuration_only",
    reasoningStatus: "cooldown",
    reasoningFailureCategory: "rate_limited",
    providers: { hybrid_voice_ready: false },
    options: { hybrid: false },
    blockers: ["Deepgram streaming STT", " OpenAI structured agent "],
  });
  assert.equal(parseRuntimeReadiness({ status: "unknown" }), null);
  assert.equal(parseRuntimeReadiness(null), null);
});

test("a microphone failure remains visible when the server reports listening", () => {
  assert.equal(resolveDisplayedVoicePhase("listening", "microphone", false, false), "error");
  assert.equal(shouldApplyServerVoicePhase("listening", "microphone", false), false);
  assert.deepEqual(resolveVoiceConnectionStatus(true, true, "microphone", false), {
    tone: "error",
    label: "Microphone issue",
  });
});

test("healthy live listening keeps the connected state", () => {
  assert.equal(resolveDisplayedVoicePhase("listening", null, false, true), "listening");
  assert.equal(resolveDisplayedVoicePhase("transcribing", null, false, true), "transcribing");
  assert.equal(shouldApplyServerVoicePhase("listening", null, true), true);
  assert.deepEqual(resolveVoiceConnectionStatus(true, true, null, true), {
    tone: "live",
    label: "Voice connected",
  });
});

test("audio output failure is visible even before the stage state rerenders", () => {
  assert.equal(resolveDisplayedVoicePhase("speaking", null, true, false), "error");
});

test("provider credit exhaustion explains the real blocker without offering a futile retry", () => {
  assert.match(resolveAudioUnavailableMessage("tts_insufficient_credits"), /credits are exhausted/i);
  assert.equal(shouldOfferVoiceRetry("tts_insufficient_credits"), false);
  assert.equal(shouldOfferVoiceRetry("tts_provider_timeout"), true);
});

test("speech provider failures show actionable credit and credential guidance", () => {
  assert.match(resolveSttUnavailableMessage("stt_finalize_timeout"), /didn't send partial words/i);
  assert.match(resolveSttUnavailableMessage("stt_finalize_timeout"), /repeat briefly or type/i);
  assert.match(resolveSttUnavailableMessage("stt_provider_unavailable"), /not ready on this server/i);
  assert.match(resolveSttUnavailableMessage("Streaming STT is not configured"), /check provider readiness/i);
  assert.match(resolveSttUnavailableMessage("stt_provider_error"), /failed before I could confirm/i);
  assert.match(resolveSttUnavailableMessage("stt_provider_insufficient_credits"), /credits are exhausted/i);
  assert.match(resolveSttUnavailableMessage("stt_provider_auth_rejected"), /rejected its credentials/i);
  assert.match(resolveSttUnavailableMessage("stt_unknown"), /reconnect or type instead/i);
});

test("an unavailable OpenAI route explains the handshake blocker and hybrid alternative", () => {
  assert.match(resolveVoiceNotReadyMessage("openai"), /check account credits/i);
  assert.match(resolveVoiceNotReadyMessage("openai"), /hybrid voice is available/i);
  assert.match(resolveVoiceNotReadyMessage("standard"), /check provider status/i);
});

test("unknown audio failures retain clear generic recovery guidance", () => {
  assert.match(resolveAudioUnavailableMessage("tts_unknown"), /spoken audio is unavailable/i);
  assert.equal(shouldOfferVoiceRetry(undefined), true);
});

test("server readiness is not shown as listening until microphone frames arrive", () => {
  assert.equal(resolveDisplayedVoicePhase("listening", null, false, false), "starting_microphone");
  assert.equal(shouldApplyServerVoicePhase("listening", null, false), false);
  assert.deepEqual(resolveVoiceConnectionStatus(true, true, null, false), {
    tone: "starting",
    label: "Microphone starting",
  });
});

test("readiness is shown as checking until the server responds", () => {
  assert.deepEqual(resolveVoiceConnectionStatus(false, false, null, false, true), {
    tone: "starting",
    label: "Checking voice",
  });
});

test("configured provider credentials are not presented as verified voice readiness", () => {
  const readiness = parseRuntimeReadiness({
    status: "ready",
    mode: "live",
    providers: { hybrid_voice_ready: true },
    live_voice: {
      verification: "configuration_only",
      options: { hybrid: true },
    },
  });
  assert.equal(readiness?.voiceVerification, "configuration_only");
  assert.deepEqual(
    resolveVoiceConnectionStatus(false, true, null, false, false, readiness?.voiceVerification),
    { tone: "unverified", label: "Route configured" },
  );
  assert.deepEqual(
    resolveVoiceConnectionStatus(true, true, null, true, false, readiness?.voiceVerification),
    { tone: "live", label: "Voice connected" },
  );
});

test("a failed readiness request does not remain stuck in checking state", () => {
  assert.deepEqual(resolveVoiceConnectionStatus(false, false, null, false, false), {
    tone: "offline",
    label: "Voice offline",
  });
});
