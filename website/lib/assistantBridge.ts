export const ASSISTANT_BRIDGE_CHANNEL = "awaaz-assistant-bridge";
export const ASSISTANT_BRIDGE_VERSION = 1;
export const ASSISTANT_MESSAGE_MAX_LENGTH = 1000;

export type AssistantPhase =
  | "idle"
  | "connecting"
  | "listening"
  | "transcribing"
  | "thinking"
  | "speaking"
  | "error";

const phases = new Set<AssistantPhase>([
  "idle",
  "connecting",
  "listening",
  "transcribing",
  "thinking",
  "speaking",
  "error",
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasEnvelope(value: unknown): boolean {
  return (
    isRecord(value) &&
    value.channel === ASSISTANT_BRIDGE_CHANNEL &&
    value.version === ASSISTANT_BRIDGE_VERSION
  );
}

function hasExactlyKeys(value: Record<string, unknown>, keys: string[]): boolean {
  const actual = Object.keys(value).sort();
  return (
    actual.length === keys.length &&
    actual.every((key, index) => key === [...keys].sort()[index])
  );
}

export interface SubmitTextMessage {
  channel: string;
  version: number;
  type: "submit_text";
  text: string;
}

export interface HelloMessage {
  channel: string;
  version: number;
  type: "hello";
}

export interface FrameStatusMessage {
  channel: string;
  version: number;
  type: "ready" | "state";
  phase: AssistantPhase;
}

export function createSubmitTextMessage(text: string): SubmitTextMessage {
  return {
    channel: ASSISTANT_BRIDGE_CHANNEL,
    version: ASSISTANT_BRIDGE_VERSION,
    type: "submit_text",
    text,
  };
}

export function createHelloMessage(): HelloMessage {
  return {
    channel: ASSISTANT_BRIDGE_CHANNEL,
    version: ASSISTANT_BRIDGE_VERSION,
    type: "hello",
  };
}

export function createFrameStatusMessage(
  type: "ready" | "state",
  phase: AssistantPhase
): FrameStatusMessage {
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

export function hasTrustedMessageOriginAndSource(
  event: unknown,
  expectedSource: Window | null,
  allowedOrigins: string[]
): boolean {
  if (!isRecord(event)) return false;
  return (
    event.source === expectedSource &&
    typeof event.origin === "string" &&
    allowedOrigins.includes(event.origin)
  );
}

export function parseParentMessage(value: unknown): HelloMessage | SubmitTextMessage | null {
  if (!hasEnvelope(value) || !isRecord(value)) {
    return null;
  }

  if (value.type === "hello" && hasExactlyKeys(value, ["channel", "version", "type"])) {
    return createHelloMessage();
  }

  if (
    !hasExactlyKeys(value, ["channel", "version", "type", "text"]) ||
    value.type !== "submit_text" ||
    typeof value.text !== "string"
  ) {
    return null;
  }

  const text = value.text.trim();
  if (text.length === 0 || text.length > ASSISTANT_MESSAGE_MAX_LENGTH) {
    return null;
  }

  return createSubmitTextMessage(text);
}

export function parseFrameMessage(value: unknown): FrameStatusMessage | null {
  if (
    !hasEnvelope(value) ||
    !isRecord(value) ||
    !hasExactlyKeys(value, ["channel", "version", "type", "phase"]) ||
    (value.type !== "ready" && value.type !== "state") ||
    typeof value.phase !== "string" ||
    !phases.has(value.phase as AssistantPhase)
  ) {
    return null;
  }

  return createFrameStatusMessage(value.type as "ready" | "state", value.phase as AssistantPhase);
}

export type AssistantActionKind =
  | "filter_catalog"
  | "compare_properties"
  | "shortlist_property"
  | "calculate_mortgage"
  | "schedule_viewing"
  | "navigate_to";

export interface AssistantActionPayload {
  [key: string]: unknown;
}

export interface AssistantAction {
  id: string;
  kind: AssistantActionKind;
  payload: AssistantActionPayload;
  summary: string;
  executed: boolean;
}

export interface ActionExecutedMessage {
  channel: string;
  version: number;
  type: "action_executed";
  action: AssistantAction;
}

export function createActionExecutedMessage(action: AssistantAction): ActionExecutedMessage {
  return {
    channel: ASSISTANT_BRIDGE_CHANNEL,
    version: ASSISTANT_BRIDGE_VERSION,
    type: "action_executed",
    action,
  };
}

export function parseActionMessage(value: unknown): ActionExecutedMessage | null {
  if (
    !hasEnvelope(value) ||
    !isRecord(value) ||
    value.type !== "action_executed" ||
    !isRecord(value.action)
  ) {
    return null;
  }
  const action = value.action as unknown as AssistantAction;
  if (!action.kind || typeof action.kind !== "string") {
    return null;
  }
  return {
    channel: ASSISTANT_BRIDGE_CHANNEL,
    version: ASSISTANT_BRIDGE_VERSION,
    type: "action_executed",
    action,
  };
}
