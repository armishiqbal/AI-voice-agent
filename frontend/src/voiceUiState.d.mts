export function resolveDisplayedVoicePhase(
  phase: string,
  failureStage: string | null,
  audioOutputUnavailable: boolean,
  audioAvailable: boolean,
): string;

export type RuntimeReadiness = {
  ready: boolean;
  mode: string;
  voiceVerification: string | null;
  reasoningStatus: string | null;
  reasoningFailureCategory: string | null;
  providers: Record<string, boolean>;
  options: Record<string, boolean>;
  blockers: string[];
};

export function parseRuntimeReadiness(value: unknown): RuntimeReadiness | null;

export function resolveVoiceNotReadyMessage(mode: string): string;

export function shouldApplyServerVoicePhase(
  nextPhase: string,
  failureStage: string | null,
  audioAvailable: boolean,
): boolean;

export function resolveVoiceConnectionStatus(
  connected: boolean,
  ready: boolean,
  failureStage: string | null,
  audioAvailable: boolean,
  readinessChecking?: boolean,
  voiceVerification?: string | null,
): { tone: "error" | "starting" | "live" | "ready" | "unverified" | "offline"; label: string };

export function resolveAudioUnavailableMessage(reason: string | undefined): string;

export function resolveSttUnavailableMessage(reason: string | undefined): string;

export function shouldOfferVoiceRetry(reason: string | undefined): boolean;
