export type AssistantPhase =
  | "idle"
  | "connecting"
  | "listening"
  | "transcribing"
  | "thinking"
  | "speaking"
  | "error";

type AssistantBridgeEnvelope = {
  channel: "awaaz-assistant-bridge";
  version: 1;
};

export type AssistantParentMessage = AssistantBridgeEnvelope
  & ({ type: "hello" } | { type: "submit_text"; text: string });

export type AssistantFrameMessage = {
  channel: "awaaz-assistant-bridge";
  version: 1;
  type: "ready" | "state";
  phase: AssistantPhase;
};

export const ASSISTANT_BRIDGE_CHANNEL: "awaaz-assistant-bridge";
export const ASSISTANT_BRIDGE_VERSION: 1;
export const ASSISTANT_MESSAGE_MAX_LENGTH: 1000;

export type AssistantActionKind =
  | "filter_catalog"
  | "compare_properties"
  | "shortlist_property"
  | "calculate_mortgage"
  | "schedule_viewing"
  | "navigate_to";

export type AssistantAction = {
  id?: string;
  kind: AssistantActionKind;
  payload: Record<string, unknown>;
  summary?: string;
  executed?: boolean;
  status?: "executed" | "undone" | "confirmed";
};

export type ActionExecutedMessage = AssistantBridgeEnvelope & {
  type: "action_executed";
  action: AssistantAction;
};

export function createSubmitTextMessage(text: string): AssistantBridgeEnvelope & { type: "submit_text"; text: string };
export function createHelloMessage(): AssistantBridgeEnvelope & { type: "hello" };
export function createFrameStatusMessage(
  type: "ready" | "state",
  phase: AssistantPhase,
): AssistantFrameMessage;
export function createActionExecutedMessage(action: AssistantAction): ActionExecutedMessage;
export function parseParentMessage(value: unknown): AssistantParentMessage | null;
export function parseFrameMessage(value: unknown): AssistantFrameMessage | null;
export function parseActionMessage(value: unknown): ActionExecutedMessage | null;
export function hasTrustedMessageOriginAndSource(
  event: { source: unknown; origin: string },
  expectedSource: unknown,
  allowedOrigins: readonly string[],
): boolean;
