const failureLabels = {
  session: "Voice issue",
  microphone: "Microphone issue",
  transcription: "Speech recognition issue",
  agent: "Agent reply issue",
  playback: "Audio playback issue",
};

function booleanRecord(value) {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return {};
  return Object.fromEntries(Object.entries(value).filter((entry) => typeof entry[1] === "boolean"));
}

export function parseRuntimeReadiness(value) {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return null;
  if (value.status !== "ready" && value.status !== "degraded") return null;

  const liveVoice = typeof value.live_voice === "object" && value.live_voice !== null && !Array.isArray(value.live_voice)
    ? value.live_voice
    : {};
  const reasoning = typeof value.structured_reasoning === "object" && value.structured_reasoning !== null && !Array.isArray(value.structured_reasoning)
    ? value.structured_reasoning
    : {};
  return {
    ready: value.status === "ready",
    mode: typeof value.mode === "string" ? value.mode : "unknown",
    voiceVerification: typeof liveVoice.verification === "string" ? liveVoice.verification : null,
    reasoningStatus: typeof reasoning.status === "string" ? reasoning.status : null,
    reasoningFailureCategory: typeof reasoning.last_failure_category === "string" ? reasoning.last_failure_category : null,
    providers: booleanRecord(value.providers),
    options: booleanRecord(liveVoice.options),
    blockers: Array.isArray(liveVoice.blockers)
      ? liveVoice.blockers.filter((blocker) => typeof blocker === "string" && blocker.trim().length > 0)
      : [],
  };
}

export function resolveVoiceNotReadyMessage(mode) {
  if (mode === "openai") {
    return "OpenAI Realtime voice could not pass its provider handshake. Check account credits and provider access, then retry. UrduLish hybrid voice is available when its status is ready.";
  }
  return "Live voice service is not ready. Check provider status before retrying.";
}

export function resolveDisplayedVoicePhase(phase, failureStage, audioOutputUnavailable, audioAvailable) {
  if (audioOutputUnavailable || failureStage !== null) return "error";
  if (phase === "listening" && !audioAvailable) return "starting_microphone";
  return phase;
}

export function shouldApplyServerVoicePhase(nextPhase, failureStage, audioAvailable) {
  if (failureStage !== null && nextPhase !== "thinking") return false;
  return nextPhase !== "listening" || audioAvailable;
}

export function resolveVoiceConnectionStatus(
  connected,
  ready,
  failureStage,
  audioAvailable,
  readinessChecking = false,
  voiceVerification = null,
) {
  if (failureStage !== null) {
    return { tone: "error", label: failureLabels[failureStage] ?? "Voice issue" };
  }
  if (connected && !audioAvailable) return { tone: "starting", label: "Microphone starting" };
  if (connected) return { tone: "live", label: "Voice connected" };
  if (readinessChecking) return { tone: "starting", label: "Checking voice" };
  if (ready && voiceVerification !== "provider_verified") {
    return { tone: "unverified", label: "Route configured" };
  }
  return ready
    ? { tone: "ready", label: "Voice ready" }
    : { tone: "offline", label: "Voice offline" };
}

export function resolveAudioUnavailableMessage(reason) {
  if (reason === "tts_insufficient_credits") {
    return "Voice provider credits are exhausted. Text chat still works; add provider credits or configure a funded speech provider before retrying.";
  }
  if (reason === "tts_rate_limited") {
    return "The speech provider is receiving too many requests. Wait a moment, then retry voice.";
  }
  if (reason === "tts_auth_rejected") {
    return "The speech provider rejected its credentials. Check the server-side provider configuration.";
  }
  return "The reply text is ready, but spoken audio is unavailable.";
}

export function resolveSttUnavailableMessage(reason) {
  if (reason === "stt_provider_insufficient_credits") {
    return "Speech provider credits are exhausted. Add provider credits or choose a funded speech recognition route, then reconnect.";
  }
  if (reason === "stt_provider_rate_limited") {
    return "Speech recognition is rate limited. Wait a moment, then reconnect.";
  }
  if (reason === "stt_provider_auth_rejected") {
    return "Speech recognition rejected its credentials. Check the server provider configuration.";
  }
  if (reason === "stt_provider_timeout") {
    return "Speech recognition did not connect in time. Check the provider and network, then retry.";
  }
  return "Speech recognition is unavailable. Reconnect or type instead.";
}

export function shouldOfferVoiceRetry(reason) {
  return reason !== "tts_insufficient_credits";
}
