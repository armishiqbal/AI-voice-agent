export const ASSISTANT_BRIDGE_CHANNEL = "awaaz-assistant-bridge";
export const ASSISTANT_BRIDGE_VERSION = 1;
export const ASSISTANT_MESSAGE_MAX_LENGTH = 1000;

const phases = new Set([
  "idle",
  "connecting",
  "listening",
  "transcribing",
  "thinking",
  "speaking",
  "error",
]);

function isRecord(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasEnvelope(value) {
  return isRecord(value)
    && value.channel === ASSISTANT_BRIDGE_CHANNEL
    && value.version === ASSISTANT_BRIDGE_VERSION;
}

function hasExactlyKeys(value, keys) {
  const actual = Object.keys(value).sort();
  return actual.length === keys.length && actual.every((key, index) => key === [...keys].sort()[index]);
}

export function createSubmitTextMessage(text) {
  return {
    channel: ASSISTANT_BRIDGE_CHANNEL,
    version: ASSISTANT_BRIDGE_VERSION,
    type: "submit_text",
    text,
  };
}

export function createHelloMessage() {
  return {
    channel: ASSISTANT_BRIDGE_CHANNEL,
    version: ASSISTANT_BRIDGE_VERSION,
    type: "hello",
  };
}

export function createFrameStatusMessage(type, phase) {
  if (type !== "ready" && type !== "state") {
    throw new TypeError("Unsupported assistant frame message type");
  }

  if (!phases.has(phase)) {
    throw new TypeError("Unsupported assistant conversation phase");
  }

  return {
    channel: ASSISTANT_BRIDGE_CHANNEL,
    version: ASSISTANT_BRIDGE_VERSION,
    type,
    phase,
  };
}

export function hasTrustedMessageOriginAndSource(event, expectedSource, allowedOrigins) {
  return isRecord(event)
    && event.source === expectedSource
    && typeof event.origin === "string"
    && allowedOrigins.includes(event.origin);
}

export function parseParentMessage(value) {
  if (!hasEnvelope(value) || !isRecord(value)) {
    return null;
  }

  if (value.type === "hello" && hasExactlyKeys(value, ["channel", "version", "type"])) {
    return createHelloMessage();
  }

  if (!hasExactlyKeys(value, ["channel", "version", "type", "text"])
    || value.type !== "submit_text"
    || typeof value.text !== "string") return null;

  const text = value.text.trim();
  if (text.length === 0 || text.length > ASSISTANT_MESSAGE_MAX_LENGTH) {
    return null;
  }

  return createSubmitTextMessage(text);
}

export function parseFrameMessage(value) {
  if (!hasEnvelope(value)
    || !hasExactlyKeys(value, ["channel", "version", "type", "phase"])
    || (value.type !== "ready" && value.type !== "state")
    || typeof value.phase !== "string"
    || !phases.has(value.phase)) {
    return null;
  }

  return createFrameStatusMessage(value.type, value.phase);
}

export function createActionExecutedMessage(action) {
  return {
    channel: ASSISTANT_BRIDGE_CHANNEL,
    version: ASSISTANT_BRIDGE_VERSION,
    type: "action_executed",
    action,
  };
}

export function parseActionMessage(value) {
  if (
    !hasEnvelope(value) ||
    !isRecord(value) ||
    value.type !== "action_executed" ||
    !isRecord(value.action)
  ) {
    return null;
  }
  return {
    channel: ASSISTANT_BRIDGE_CHANNEL,
    version: ASSISTANT_BRIDGE_VERSION,
    type: "action_executed",
    action: value.action,
  };
}

