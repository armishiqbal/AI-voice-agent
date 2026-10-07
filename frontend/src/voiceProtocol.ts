export type AgentDecision = {
  kind: string;
  spoken_text: string;
  property_ids?: string[];
  reason?: string | null;
  actions?: Array<{
    id?: string;
    kind: string;
    payload?: Record<string, unknown>;
    summary?: string;
    executed?: boolean;
  }>;
};

export type AcousticEmotion = {
  emotion: string;
  speech_rate: number;
  pitch_offset: number;
  fish_audio_tag: string;
  prompt_guidance: string;
  description: string;
};

export type ServerEvent = {
  type: string;
  response_id?: number;
  recoverable?: boolean;
  restart_required?: boolean;
  state?: string;
  text?: string;
  confidence?: number | null;
  is_final?: boolean;
  speech_final?: boolean;
  acknowledgement?: boolean;
  audio_base64?: string;
  encoding?: string;
  sample_rate?: number;
  decision?: AgentDecision;
  emotion?: AcousticEmotion;
  audio_input_available?: boolean;
  interrupt_playback?: boolean;
  voice_mode?: string;
  message?: string;
  reason?: string;
  reasoning_status?: "unconfigured" | "configured_unverified" | "cooldown" | "provider_error";
  reasoning_failure_category?: "rate_limited" | "authentication_failed" | "timeout" | "invalid_response" | "provider_error" | null;
  ready?: boolean;
  property_id?: string;
  slots?: string[];
  status?: string;
  reference?: string;
  starts_at?: string;
  action?: "cancellation" | "reschedule";
  latency_ms?: number;
};

export const MAX_SERVER_EVENT_CHARS = 1_048_576;
export const AUDIO_UPLINK_HIGH_WATER_BYTES = 256 * 1024;

export type AudioUplinkState = "ready" | "backpressured" | "closed";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isOptionalString(value: unknown): boolean {
  return value === undefined || typeof value === "string";
}

function isOptionalReasoningStatus(value: unknown): value is ServerEvent["reasoning_status"] {
  return value === undefined
    || value === "unconfigured"
    || value === "configured_unverified"
    || value === "cooldown"
    || value === "provider_error";
}

function isOptionalReasoningFailureCategory(value: unknown): value is ServerEvent["reasoning_failure_category"] {
  return value === undefined
    || value === null
    || value === "rate_limited"
    || value === "authentication_failed"
    || value === "timeout"
    || value === "invalid_response"
    || value === "provider_error";
}

function isOptionalBoolean(value: unknown): boolean {
  return value === undefined || typeof value === "boolean";
}

function isAudioDecision(value: unknown): value is AgentDecision {
  if (!isRecord(value) || typeof value.kind !== "string" || typeof value.spoken_text !== "string") {
    return false;
  }
  if (value.spoken_text.length > 2_000) return false;
  if (value.reason !== undefined && value.reason !== null && typeof value.reason !== "string") {
    return false;
  }
  return value.property_ids === undefined
    || (Array.isArray(value.property_ids)
      && value.property_ids.length <= 20
      && value.property_ids.every((id) => typeof id === "string" && id.length <= 128));
}

function isPcmOrMpegBase64(value: unknown): value is string {
  return typeof value === "string"
    && value.length <= MAX_SERVER_EVENT_CHARS
    && /^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(value);
}

export function parseServerEvent(data: unknown): ServerEvent | null {
  if (typeof data !== "string" || data.length > MAX_SERVER_EVENT_CHARS) return null;
  let value: unknown;
  try {
    value = JSON.parse(data) as unknown;
  } catch {
    return null;
  }
  if (!isRecord(value) || typeof value.type !== "string") return null;

  if (value.response_id !== undefined && (!Number.isSafeInteger(value.response_id) || (value.response_id as number) < 1)) return null;
  if (!isOptionalBoolean(value.recoverable) || !isOptionalBoolean(value.restart_required)) return null;

  switch (value.type) {
    case "state":
      return isOptionalString(value.state)
        && isOptionalBoolean(value.audio_input_available)
        && isOptionalBoolean(value.interrupt_playback)
        ? value as ServerEvent
        : null;
    case "transcript":
    case "transcript_low_confidence":
      return typeof value.text === "string"
        && value.text.length <= 4_000
        && isOptionalString(value.state)
        && isOptionalBoolean(value.is_final)
        && isOptionalBoolean(value.speech_final)
        && (value.confidence === undefined || value.confidence === null
          || (typeof value.confidence === "number" && value.confidence >= 0 && value.confidence <= 1))
        ? value as ServerEvent
        : null;
    case "agent_response":
      return isAudioDecision(value.decision)
        && isOptionalReasoningStatus(value.reasoning_status)
        && isOptionalReasoningFailureCategory(value.reasoning_failure_category)
        ? value as ServerEvent
        : null;
    case "audio_chunk":
      return isPcmOrMpegBase64(value.audio_base64)
        && (value.encoding === "pcm_s16le" || value.encoding === "audio/mpeg")
        && typeof value.sample_rate === "number"
        && Number.isInteger(value.sample_rate)
        && value.sample_rate >= 8_000
        && value.sample_rate <= 96_000
        && isOptionalBoolean(value.acknowledgement)
        && isOptionalBoolean(value.is_final)
        ? value as ServerEvent
        : null;
    case "audio_unavailable":
    case "agent_unavailable":
    case "stt_unavailable":
      return isOptionalString(value.reason) ? value as ServerEvent : null;
    case "error":
      return isOptionalString(value.message) ? value as ServerEvent : null;
    case "booking_contact_status":
      return typeof value.ready === "boolean" ? value as ServerEvent : null;
    case "booking_slots":
      return typeof value.property_id === "string"
        && Array.isArray(value.slots)
        && value.slots.length <= 3
        && value.slots.every((slot) => typeof slot === "string" && slot.length <= 64)
        ? value as ServerEvent
        : null;
    case "appointment_result":
      return value.status === "pending_calendar"
        && (value.action === undefined || value.action === "cancellation" || value.action === "reschedule")
        && typeof value.reference === "string"
        && value.reference.length <= 32
        && typeof value.property_id === "string"
        && typeof value.starts_at === "string"
        ? value as ServerEvent
        : null;
    default:
      return null;
  }
}

export function shouldInterruptPlayback(event: ServerEvent): boolean {
  return event.type === "state"
    && event.state === "listening"
    && event.interrupt_playback === true;
}

export function audioUplinkState(
  readyState: number,
  bufferedBytes: number,
  highWaterBytes = AUDIO_UPLINK_HIGH_WATER_BYTES,
): AudioUplinkState {
  if (readyState !== 1) return "closed";
  if (!Number.isFinite(bufferedBytes) || bufferedBytes < 0 || bufferedBytes >= highWaterBytes) {
    return "backpressured";
  }
  return "ready";
}
