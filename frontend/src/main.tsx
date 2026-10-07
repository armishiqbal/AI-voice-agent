import { reviewedSizeLabel } from "./propertyFacts.mjs";
import React, { useEffect, useRef, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { NeuralOrb } from "./NeuralOrb";
import { WaveformVisualizer } from "./WaveformVisualizer";
import { BrowserAudioCapture, BrowserAudioPlayback } from "./voiceAudio";
import { parseServerEvent, shouldInterruptPlayback, audioUplinkState } from "./voiceProtocol";
import { closeVoiceSession, resolveLiveVoiceAction, shouldAutoReconnectVoice, voiceReconnectDelayMs, VoiceInputGate, VoiceResponseTracker } from "./voiceConversation";
import { BoundedAudioReplay, enqueueReplay } from "./voiceReplay";
import { voiceModeForLanguage } from "./voiceMode.mjs";
import {
  resolveAudioUnavailableMessage,
  resolveDisplayedVoicePhase,
  parseRuntimeReadiness,
  parseStructuredReasoningStatus,
  type StructuredReasoningStatus,
  type RuntimeReadiness,
  resolveSttUnavailableMessage,
  resolveVoiceNotReadyMessage,
  resolveVoiceConnectionStatus,
  shouldApplyServerVoicePhase,
  shouldOfferVoiceRetry,
} from "./voiceUiState.mjs";
import { PropertyComparisonHUD } from "./PropertyComparisonHUD";
import { MortgageCalculatorModal } from "./MortgageCalculatorModal";
import { canRequestVisit } from "./propertyFacts.mjs";
import { useNativeDialog } from "./useNativeDialog";
import {
  createActionExecutedMessage,
  createFrameStatusMessage,
  createHelloMessage,
  hasTrustedMessageOriginAndSource,
  parseParentMessage,
  type AssistantPhase,
} from "../../shared/assistantBridge.mjs";
import "./styles.css";

type Property = {
  id: string;
  title: string;
  city: string;
  area: string;
  price_pkr: number;
  bedrooms: number;
  size_sqft: number;
  purpose: string;
  amenities: string[];
  payment_plan: string;
  available: boolean;
  assigned_employee: string;
  source_version: string;
  source: string;
  publisher?: {id:string;slug:string;name:string} | null;
  rental_period?: string | null;
  sqft_per_marla?: number | null;
  slug?: string;
  photos?: Array<{ url: string; alt_text: string; sort_order: number }>;
  transaction_type?: "sale" | "rent";
  property_type?: string;
  bathrooms?: number | null;
  availability_status?: string;
  availability_confirmed_at?: string | null;
  verification?: { status: string; reviewed_at: string | null; scope: string | null; source_url?: string | null };
};

type Message = { role: "customer" | "agent"; text: string; time: string };
type VoicePhase = "checking" | "blocked" | "idle" | "connecting" | "authenticating" | "starting_microphone" | "listening" | "transcribing" | "thinking" | "speaking" | "error";
type VoiceFailureStage = "session" | "microphone" | "transcription" | "agent" | "playback";
type FeedbackTone = "info" | "pending" | "success" | "error";
type VoiceMode = "standard" | "openai" | "hybrid";

const stamp = () => new Intl.DateTimeFormat("en-PK", { hour: "numeric", minute: "2-digit" }).format(new Date());
const idempotencyKey = () => typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
  ? crypto.randomUUID()
  : `${Date.now()}-${Math.random().toString(16).slice(2)}`;


function formatPricePKR(price: number): string {
  if (price >= 10_000_000) {
    const crore = (price / 10_000_000).toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
    return `PKR ${crore} Crore`;
  }
  if (price >= 100_000) {
    const lakh = (price / 100_000).toFixed(1).replace(/\.0$/, "");
    return `PKR ${lakh} Lakh`;
  }
  return `PKR ${price.toLocaleString()}`;
}

function resolveDefaultApiUrl(): string {
  if (typeof window !== "undefined" && window.location) {
    const { protocol, hostname, port } = window.location;
    if (port === "5173" || port === "3000") {
      return `${protocol}//${hostname}:8000`;
    }
    return window.location.origin;
  }
  return "http://localhost:8000";
}

function publicWebsiteOrigin(parentOrigin: string | null): string {
  if (parentOrigin) return parentOrigin;
  const configured = import.meta.env.VITE_PUBLIC_WEBSITE_URL as string | undefined;
  if (configured) return configured.replace(/\/$/, "");
  if (import.meta.env.PROD) return window.location.origin;
  return `${window.location.protocol}//${window.location.hostname}:3000`;
}

const rawApiUrl = (import.meta.env.VITE_API_URL as string | undefined) || resolveDefaultApiUrl();
const apiUrl = rawApiUrl.replace(/\/+$/, "");
const wsUrl = (import.meta.env.VITE_WS_URL as string | undefined) || (apiUrl.replace(/^http/, "ws") + "/v1/voice");
const configuredAssistantParentOrigins = new Set(
  ((import.meta.env.VITE_ASSISTANT_PARENT_ORIGINS as string | undefined)
    || "http://localhost:3000,http://127.0.0.1:3000")
    .split(",")
    .map((origin) => origin.trim())
    .filter(Boolean),
);

function bridgePhase(phase: VoicePhase): AssistantPhase {
  if (phase === "checking" || phase === "blocked") return phase === "blocked" ? "error" : "idle";
  if (phase === "authenticating" || phase === "starting_microphone") return "connecting";
  return phase;
}

function Icon({ children }: { children: string }) {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d={children} /></svg>;
}

const paths = {
  mic: "M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Zm-7 9a7 7 0 0 0 14 0M12 18v4M8 22h8",
  phone: "M22 16.92v3a2 2 0 0 1-2.18 2 19.8 19.8 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.12 4.18 2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.12.9.33 1.77.62 2.6a2 2 0 0 1-.45 2.11L8.01 9.7a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.83.29 1.7.5 2.6.62A2 2 0 0 1 22 16.92Z",
  send: "m22 2-7 20-4-9-9-4Z M22 2 11 13",
  spark: "m12 3-1.9 5.1L5 10l5.1 1.9L12 17l1.9-5.1L19 10l-5.1-1.9L12 3Z",
  volume: "M11 5 6 9H2v6h4l5 4V5Zm4.5 3.5a5 5 0 0 1 0 7",
  stop: "M7 7h10v10H7z",
  home: "m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z",
  calendar: "M8 2v4m8-4v4M3 10h18M5 4h14a2 2 0 0 1 2 2v14H3V6a2 2 0 0 1 2-2Z",
  transcript: "M4 5h16M4 10h16M4 15h10M4 20h7",
  copy: "M8 8h11v13H8z M5 16H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1",
  close: "M18 6 6 18 M6 6l12 12",
  building: "M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z M6 12h12 M6 7h12 M6 17h12",
  settings: "M10.8 2h2.4l.48 2.1a8 8 0 0 1 1.63.68l1.92-1.1 1.7 1.7-1.1 1.92c.29.5.52 1.05.68 1.63l2.1.48v2.4l-2.1.48a8 8 0 0 1-.68 1.63l1.1 1.92-1.7 1.7-1.92-1.1a8 8 0 0 1-1.63.68l-.48 2.1h-2.4l-.48-2.1a8 8 0 0 1-1.63-.68l-1.92 1.1-1.7-1.7 1.1-1.92a8 8 0 0 1-.68-1.63l-2.1-.48v-2.4l2.1-.48a8 8 0 0 1 .68-1.63l-1.1-1.92 1.7-1.7 1.92 1.1a8 8 0 0 1 1.63-.68L10.8 2Z M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z",
  chart: "M4 19V5m0 14h17M8 15l3-4 3 2 5-7",
  compare: "M4 4h6v16H4zM14 4h6v16h-6zM6 8h2M6 12h2M6 16h2M16 8h2M16 12h2M16 16h2",
};

const voicePhaseLabels: Record<VoicePhase, string> = {
  checking: "Checking live voice service…",
  blocked: "Live voice is unavailable. Check provider readiness before starting a call.",
  idle: "Ready when you are — start a voice conversation or type a question",
  connecting: "Connecting voice session…",
  authenticating: "Authenticating security token…",
  starting_microphone: "Starting microphone…",
  listening: "Listening… Speak your requirement",
  transcribing: "Finishing speech recognition…",
  thinking: "Searching available inventory…",
  speaking: "Awaaz Estate is responding…",
  error: "Voice connection failed. Use the voice button to reconnect.",
};

function microphoneFailureMessage(error: unknown): string {
  const name = error instanceof Error ? error.name : "UnknownError";
  switch (name) {
    case "NotAllowedError":
    case "SecurityError":
      return "Microphone permission was denied. Allow microphone access for this site, then retry.";
    case "NotFoundError":
    case "DevicesNotFoundError":
      return "No microphone was found. Connect or select an input device, then retry.";
    case "NotReadableError":
    case "TrackStartError":
      return "The microphone is busy or unavailable. Close other apps using it, then retry.";
    case "OverconstrainedError":
      return "The selected microphone is unavailable. Choose System default in Voice Settings, then retry.";
    case "NotSupportedError":
      return "This browser cannot start the voice capture worklet. Update the browser and retry.";
    default:
      return `Microphone setup failed (${name}). Check site permission and the selected input, then retry.`;
  }
}

function App() {
  const [activeActionLabel, setActiveActionLabel] = useState<string>("Ready when you are");
  const [audioUnavailableReason, setAudioUnavailableReason] = useState<string | undefined>();
  const [subtitles, setSubtitles] = useState("");
  const [canReplayResponse, setCanReplayResponse] = useState(false);
  const [liveTranscript, setLiveTranscript] = useState("");
  const [voicePhase, setVoicePhase] = useState<VoicePhase>("checking");
  const voicePhaseRef = useRef(voicePhase);
  useEffect(() => { voicePhaseRef.current = voicePhase; }, [voicePhase]);
  const voiceFailureStageRef = useRef<VoiceFailureStage | null>(null);
  const [voiceFailureStage, setVoiceFailureStageState] = useState<VoiceFailureStage | null>(null);
  const setVoiceFailureStage = (stage: VoiceFailureStage | null) => {
    voiceFailureStageRef.current = stage;
    setVoiceFailureStageState(stage);
  };
  const [transcriptFinalized, setTranscriptFinalized] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationFailed, setConversationFailed] = useState(false);
  const [conversationCopyStatus, setConversationCopyStatus] = useState("");
  const [matches, setMatches] = useState<string[]>([]);
  const [propertyDetails, setPropertyDetails] = useState<Record<string, Property>>({});
  const [loadingPropertyIds, setLoadingPropertyIds] = useState<string[]>([]);
  const [socket, setSocket] = useState<WebSocket | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [language, setLanguage] = useState<"ur-Latn" | "ur-Arab" | "en" | "hi" | "ar" | "pa" | "bn">("ur-Latn");
  const voiceMode: VoiceMode = voiceModeForLanguage(language);
  const audioAvailableRef = useRef(false);
  const [audioAvailable, setAudioAvailableState] = useState(false);
  const setAudioAvailable = (available: boolean) => {
    audioAvailableRef.current = available;
    setAudioAvailableState(available);
  };
  const [microphoneSignal, setMicrophoneSignal] = useState<"checking" | "detected" | "silent">("checking");
  const [audioInputs, setAudioInputs] = useState<MediaDeviceInfo[]>([]);
  const [selectedInputId, setSelectedInputId] = useState("");
  const [audioOutputUnavailable, setAudioOutputUnavailable] = useState(false);
  const audioOutputUnavailableRef = useRef(false);
  const [appointmentStatus, setAppointmentStatus] = useState("");
  const [appointmentTone, setAppointmentTone] = useState<FeedbackTone>("info");
  const [runtimeReadiness, setRuntimeReadiness] = useState<RuntimeReadiness | null>(null);
  const [reasoningProviderStatus, setReasoningProviderStatus] = useState<StructuredReasoningStatus | null>(null);
  const [readinessCheckFailed, setReadinessCheckFailed] = useState(false);
  const [readinessRefreshKey, setReadinessRefreshKey] = useState(0);
  const [selectedPropertyId, setSelectedPropertyId] = useState<string>("");
  const [showDrawer, setShowDrawer] = useState(true);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [matchMessage, setMatchMessage] = useState("");
  const [inquiryPropertyId, setInquiryPropertyId] = useState<string | null>(null);
  const [inquiryStatus, setInquiryStatus] = useState("");
  const [inquiryForm, setInquiryForm] = useState({ name: "", email: "", message: "", consent: false });
  const [comparedPropertyIds, setComparedPropertyIds] = useState<string[]>([]);
  const [showCompareHUD, setShowCompareHUD] = useState(false);
  const [showMortgageCalc, setShowMortgageCalc] = useState(false);
  const [mortgageCustomProperty, setMortgageCustomProperty] = useState<Property | null>(null);
  const [mortgageCustomDownPct, setMortgageCustomDownPct] = useState<number | undefined>(undefined);
  const [mortgageCustomTenureYears, setMortgageCustomTenureYears] = useState<number | undefined>(undefined);
  const [lastTiming, setLastTiming] = useState<{ label: string; milliseconds: number } | null>(null);
  const [agentDecisionLatencyMs, setAgentDecisionLatencyMs] = useState<number | null>(null);
  const [substantiveAnswerLatencyMs, setSubstantiveAnswerLatencyMs] = useState<number | null>(null);
  const [audioAnalyser, setAudioAnalyser] = useState<AnalyserNode | null>(null);
  const httpTurnAbort = useRef<AbortController | null>(null);
  const bridgeParentOrigin = useRef<string | null>(null);
  const sendMessageRef = useRef<(text?: string) => Promise<void>>(async () => undefined);
  const lastSubmittedText = useRef("");

  const [appointmentForm, setAppointmentForm] = useState({
    client_name: "",
    contact_email: "",
    contact_phone: "",
    starts_at: "",
    consent: false,
  });
  const [viewingSlots, setViewingSlots] = useState<string[]>([]);
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [viewingOtp, setViewingOtp] = useState("");
  const [viewingVerificationToken, setViewingVerificationToken] = useState("");
  const [viewingOtpMessage, setViewingOtpMessage] = useState("");
  const [viewingEmailVerified, setViewingEmailVerified] = useState(false);

  const conversationId = useRef(
    typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `conv-${Date.now()}`
  );
  const bookingDialog = useRef<HTMLDialogElement | null>(null);
  const inquiryDialog = useRef<HTMLDialogElement | null>(null);
  const inquiryIdempotencyKey = useRef(idempotencyKey());
  const viewingIdempotencyKey = useRef(idempotencyKey());
  const textInputRef = useRef<HTMLInputElement | null>(null);
  const settingsDialog = useNativeDialog(showSettingsModal);
  const replayAudio = useRef(new BoundedAudioReplay());
  const capture = useRef<BrowserAudioCapture | null>(null);
  const finishSpeech = useRef<(() => void) | null>(null);
  const voiceTurnEndedAt = useRef<number | null>(null);
  const answerAudioOriginAt = useRef<number | null>(null);
  const voiceTimingOrigin = useRef<"voice" | "text" | null>(null);
  const selectedInputRef = useRef("");
  const acknowledgementAudioPending = useRef(false);
  const playback = useRef(new BrowserAudioPlayback({
    onStart: () => {
      if (voiceTurnEndedAt.current !== null) {
        const origin = voiceTimingOrigin.current;
        const wasAcknowledgement = acknowledgementAudioPending.current;
        setLastTiming({
          label: wasAcknowledgement ? "Voice → acknowledgement" : origin === "text" ? "Text → audio" : "Voice → audio",
          milliseconds: Math.round(performance.now() - voiceTurnEndedAt.current),
        });
        voiceTurnEndedAt.current = null;
        voiceTimingOrigin.current = null;
      }
      setVoicePhase("speaking");
      setActiveActionLabel(acknowledgementAudioPending.current
        ? "I heard you. Checking the live details now…"
        : "Awaaz is speaking. You can interrupt at any time.");
      acknowledgementAudioPending.current = false;
    },
    onDrain: () => {
      if (voicePhaseRef.current === "transcribing") return;
      const captureReady = audioAvailableRef.current && voiceFailureStageRef.current === null;
      setVoicePhase(serverPhase.current === "listening"
        ? captureReady ? "listening" : "starting_microphone"
        : "thinking");
      if (serverPhase.current === "listening" && captureReady && !audioOutputUnavailableRef.current) {
        setActiveActionLabel("Listening for your request");
      }
    },
    onError: () => {
      audioOutputUnavailableRef.current = true;
      setAudioOutputUnavailable(true);
      setVoiceFailureStage("playback");
      setVoicePhase("error");
      setActiveActionLabel("Audio did not play. The reply text is available below.");
    },
  }));
  const responses = useRef(new VoiceResponseTracker());
  const serverPhase = useRef<VoicePhase>("idle");
  const sttRestarts = useRef(0);
  const languageRef = useRef(language);
  const voiceModeRef = useRef<VoiceMode>(voiceMode);
  const reconnectAfterLanguageChange = useRef(false);
  const sessionRequestedRef = useRef(false);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<number | null>(null);
  const messageListRef = useRef<HTMLDivElement | null>(null);

  const connected = socket?.readyState === WebSocket.OPEN;
  const sessionReady = connected && voicePhase !== "authenticating";
  const readinessKey = voiceMode === "openai"
    ? "openai_voice_ready"
    : voiceMode === "hybrid" ? "hybrid_voice_ready" : "standard_voice_ready";
  const voiceReady = runtimeReadiness?.providers[readinessKey] === true;
  const displayVoicePhase = resolveDisplayedVoicePhase(voicePhase, voiceFailureStage, audioOutputUnavailable, audioAvailable) as VoicePhase;
  const connectionStatus = resolveVoiceConnectionStatus(
    connected,
    voiceReady,
    voiceFailureStage,
    audioAvailable,
    runtimeReadiness === null && !readinessCheckFailed,
    runtimeReadiness?.voiceVerification,
  );
  const microphoneStageState = microphoneSignal === "silent"
    ? "warning"
    : audioAvailable ? "done" : voiceFailureStage === "microphone" ? "failed" : sessionReady ? "active" : "waiting";
  const microphoneStageDetail = microphoneSignal === "silent"
    ? "No sound detected"
    : audioAvailable
      ? microphoneSignal === "detected" ? "Input active · sound detected" : "Input active · speak now"
      : voiceFailureStage === "microphone" ? "Check permission or device" : sessionReady ? "Starting input" : "Waiting";
  const voiceStages = [
    {
      id: "session",
      label: "Session",
      state: sessionReady ? "done" : voiceFailureStage === "session" ? "failed" : connecting || connected ? "active" : "waiting",
      detail: sessionReady ? "Connected" : voiceFailureStage === "session" ? "Connection failed" : connecting ? "Connecting" : connected ? "Authenticating" : "Waiting",
    },
    {
      id: "microphone",
      label: "Microphone",
      state: microphoneStageState,
      detail: microphoneStageDetail,
    },
    {
      id: "transcription",
      label: "Speech",
      state: transcriptFinalized ? "done" : voiceFailureStage === "transcription" ? "failed" : displayVoicePhase === "transcribing" || audioAvailable ? "active" : "waiting",
      detail: transcriptFinalized ? "Recognized" : voiceFailureStage === "transcription" ? "Recognition failed" : displayVoicePhase === "transcribing" ? "Finalizing transcript" : audioAvailable ? "Waiting for speech" : "Waiting",
    },
    {
      id: "agent",
      label: "Agent reply",
      state: subtitles ? "done" : voiceFailureStage === "agent" ? "failed" : transcriptFinalized ? "active" : "waiting",
      detail: subtitles ? "Reply ready" : voiceFailureStage === "agent" ? "Reply failed" : transcriptFinalized ? "Generating" : "Waiting",
    },
    {
      id: "playback",
      label: "Voice output",
      state: audioOutputUnavailable ? "failed" : canReplayResponse || (Boolean(subtitles) && displayVoicePhase === "listening") ? "done" : subtitles ? "active" : "waiting",
      detail: audioOutputUnavailable ? "Audio unavailable" : canReplayResponse || (Boolean(subtitles) && displayVoicePhase === "listening") ? "Audio ready" : subtitles ? "Preparing audio" : "Waiting",
    },
  ] as const;
  const availableMatches = matches.filter((id) => canRequestVisit(propertyDetails[id]));
  const appointmentSlotError = viewingSlots.includes(appointmentForm.starts_at) ? "" : "Choose a currently available viewing slot.";

  useEffect(() => {
    voiceModeRef.current = voiceMode;
  }, [voiceMode]);

  useEffect(() => {
    const trustedOrigins = new Set([...configuredAssistantParentOrigins, window.location.origin]);

    const handleParentMessage = (event: MessageEvent<unknown>) => {
      if (!hasTrustedMessageOriginAndSource(event, window.parent, [...trustedOrigins])) return;
      bridgeParentOrigin.current = event.origin;
      const message = parseParentMessage(event.data);
      if (!message) return;
      if (message.type === "hello") {
        window.parent.postMessage(
          createFrameStatusMessage("ready", bridgePhase(voicePhaseRef.current)),
          event.origin,
        );
        return;
      }
      void sendMessageRef.current(message.text);
    };

    window.addEventListener("message", handleParentMessage);

    return () => window.removeEventListener("message", handleParentMessage);
  }, []);

  useEffect(() => {
    const trustedOrigin = bridgeParentOrigin.current;
    if (!trustedOrigin) return;
    window.parent.postMessage(
      createFrameStatusMessage("state", bridgePhase(displayVoicePhase)),
      trustedOrigin,
    );
  }, [displayVoicePhase]);

  useEffect(() => {
    if (!reconnectAfterLanguageChange.current || socket || connecting) return;
    reconnectAfterLanguageChange.current = false;
    void connect();
  }, [connecting, socket, voiceMode]);

  useEffect(() => {
    const messageList = messageListRef.current;
    if (!showDrawer || !messageList || messages.length === 0) return;
    const frame = window.requestAnimationFrame(() => {
      messageList.scrollTo({ top: messageList.scrollHeight, behavior: "smooth" });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [messages, showDrawer]);

  // Load properties preview
  // Check server readiness
  useEffect(() => {
    let active = true;
    const refreshReadiness = async () => {
      try {
        const response = await fetch(`${apiUrl}/readyz`);
        if (!response.ok) throw new Error("Readiness check failed");
        const value: unknown = await response.json();
        const readiness = parseRuntimeReadiness(value);
        if (!readiness) throw new Error("Readiness response was invalid");
        if (!active) return;
        const readinessRecord = value as Record<string, unknown>;
        const reasoningStatus = parseStructuredReasoningStatus(readinessRecord.structured_reasoning);
        if (reasoningStatus) setReasoningProviderStatus(reasoningStatus);
        const configured = readiness.providers[readinessKey] === true;
        setReadinessCheckFailed(false);
        setRuntimeReadiness(readiness);
        setVoicePhase((current) =>
          ["connecting", "authenticating", "listening", "transcribing", "thinking", "speaking", "error"].includes(current)
            ? current
            : configured ? "idle" : "blocked"
        );
      } catch {
        if (active) {
          setReadinessCheckFailed(true);
          setRuntimeReadiness(null);
          setVoicePhase("blocked");
        }
      }
    };
    void refreshReadiness();
    const timer = window.setInterval(() => void refreshReadiness(), 30_000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [readinessKey, readinessRefreshKey]);

  function changeLanguage(next: "ur-Latn" | "ur-Arab" | "en" | "hi" | "ar" | "pa" | "bn") {
    const modeChanged = voiceModeForLanguage(next) !== voiceModeRef.current;
    const wasConnected = socket?.readyState === WebSocket.OPEN;
    if (modeChanged && wasConnected) {
      reconnectAfterLanguageChange.current = true;
      disconnect();
      setActiveActionLabel("Switching voice services for the selected language…");
    }
    setLanguage(next);
    languageRef.current = next;
    voiceModeRef.current = voiceModeForLanguage(next);
    if (!modeChanged && socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: "set_language", language: next }));
    }
  }

  function loadMatchedProperties(ids: string[]) {
    if (ids.length === 0) return;
    const requested = [...new Set(ids)].slice(0, 3);
    setMatchMessage("");
    setLoadingPropertyIds((current) => [...new Set([...current, ...requested])]);
    void Promise.all(requested.map(async (id) => {
      try {
        const response = await fetch(`${apiUrl}/v1/public/listings/by-id/${encodeURIComponent(id)}`);
        if (!response.ok) return { id, listing: null };
        const listing = await response.json();
        if (!listing || listing.id !== id || typeof listing.slug !== "string" || !Array.isArray(listing.photos)) {
          return { id, listing: null };
        }
        const property: Property = {
          id: listing.id,
          publisher: listing.publisher, rental_period: listing.rental_period, sqft_per_marla: listing.sqft_per_marla,
          slug: listing.slug,
          title: listing.title,
          city: listing.city,
          area: listing.area,
          price_pkr: listing.price_pkr,
          bedrooms: listing.bedrooms,
          bathrooms: listing.bathrooms,
          size_sqft: listing.size_sqft,
          purpose: listing.transaction_type,
          transaction_type: listing.transaction_type,
          property_type: listing.property_type,
          amenities: listing.amenities,
          payment_plan: "",
          available: listing.availability_status === "available",
          availability_status: listing.availability_status,
          availability_confirmed_at: listing.availability_confirmed_at,
          verification: listing.verification,
          photos: listing.photos,
          assigned_employee: "",
          source_version: "published",
          source: "published marketplace",
        };
        return { id, listing: property };
      } catch {
        return { id, listing: null };
      }
    })).then((items) => {
      const valid = items.flatMap((item) => item.listing ? [item.listing] : []);
      const stale = items.some((item) => !item.listing);
      setMatches(valid.map((item) => item.id));
      if (!valid.some((item) => item.id === selectedPropertyId)) setSelectedPropertyId(valid[0]?.id ?? "");
      setMatchMessage(stale ? "Some suggested listings changed or are no longer eligible. Ask for a fresh search to see current options." : "");
      setPropertyDetails((current) => ({
        ...current,
        ...Object.fromEntries(valid.map((item) => [item.id, item])),
      }));
    }).finally(() => {
      setLoadingPropertyIds((current) => current.filter((id) => !requested.includes(id)));
    });
  }

  async function refreshViewingSlots(propertyId: string) {
    setSlotsLoading(true);
    setViewingSlots([]);
    try {
      const response = await fetch(`${apiUrl}/v1/public/listings/${encodeURIComponent(propertyId)}/slots`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Viewing slots could not be loaded.");
      const slots = Array.isArray(data.data) ? data.data.filter((slot: unknown): slot is string => typeof slot === "string") : [];
      setViewingSlots(slots);
      setAppointmentForm((current) => ({ ...current, starts_at: slots[0] ?? "" }));
      if (slots.length === 0) setAppointmentStatus("No current viewing slots are available. You can still send an inquiry.");
    } catch (error) {
      setAppointmentStatus(error instanceof Error ? error.message : "Viewing slots could not be loaded.");
    } finally {
      setSlotsLoading(false);
    }
  }

  async function requestViewingOtp() {
    const email = appointmentForm.contact_email.trim();
    if (!email) {
      setAppointmentTone("error");
      setViewingOtpMessage("Enter your email address first.");
      return;
    }
    setViewingOtpMessage("Requesting a verification code…");
    try {
      const response = await fetch(`${apiUrl}/v1/public/viewings/request-otp`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Verification email could not be requested.");
      setViewingOtpMessage(data.message || "Check your email for the verification code.");
      if (typeof data.debug_otp === "string" && import.meta.env.DEV) {
        setViewingOtpMessage(`${data.message} Local development code: ${data.debug_otp}`);
      }
      setViewingEmailVerified(false);
      setViewingVerificationToken("");
    } catch (error) {
      setViewingOtpMessage(error instanceof Error ? error.message : "Verification email could not be requested.");
    }
  }

  async function verifyViewingOtp() {
    try {
      const response = await fetch(`${apiUrl}/v1/public/viewings/verify-otp`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: appointmentForm.contact_email.trim(), otp: viewingOtp.trim() }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "That code could not be verified.");
      setViewingVerificationToken(data.verification_token);
      setViewingEmailVerified(true);
      setViewingOtpMessage("Email verified for this viewing request.");
    } catch (error) {
      setViewingEmailVerified(false);
      setViewingVerificationToken("");
      setViewingOtpMessage(error instanceof Error ? error.message : "That code could not be verified.");
    }
  }

  async function startCapture(ws: WebSocket, mode: VoiceMode) {
    const nextCapture = new BrowserAudioCapture();
    capture.current = nextCapture;
    setMicrophoneSignal("checking");
    const inputGate = new VoiceInputGate();
    let audioSessionStarted = false;
    let stoppedForBackpressure = false;
    let manuallyCommitted = false;
    let firstCaptureFrameSeen = false;
    let silentInputMs = 0;
    let inputSignalSeen = false;
    finishSpeech.current = () => {
      if (capture.current !== nextCapture || ws.readyState !== WebSocket.OPEN) return;
      manuallyCommitted = true;
      voicePhaseRef.current = "transcribing";
      setVoicePhase("transcribing");
      voiceTurnEndedAt.current = performance.now();
      answerAudioOriginAt.current = voiceTurnEndedAt.current;
      voiceTimingOrigin.current = "voice";
      inputGate.end();
      ws.send(JSON.stringify({ type: "audio_turn_end" }));
      setActiveActionLabel("Processing your speech…");
    };
    try {
      await nextCapture.start(
        (chunk) => {
          if (stoppedForBackpressure || capture.current !== nextCapture) return;
          if (!firstCaptureFrameSeen) {
            firstCaptureFrameSeen = true;
            reconnectAttemptRef.current = 0;
            setAudioAvailable(true);
            setVoiceFailureStage(null);
            setAudioAnalyser(nextCapture.getAnalyser());
            if (serverPhase.current === "listening") {
              setVoicePhase("listening");
              setActiveActionLabel("Microphone connected. Speak naturally.");
            }
          }
          const uplinkState = audioUplinkState(ws.readyState, ws.bufferedAmount);
          if (uplinkState !== "ready") {
            stoppedForBackpressure = true;
            nextCapture.stop();
            capture.current = null;
            finishSpeech.current = null;
            if (audioSessionStarted && ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({ type: "audio_end" }));
            }
            setAudioAvailable(false);
            setActiveActionLabel("Voice paused because the connection is slow.");
            return;
          }
          try {
            const frames = mode === "openai" ? inputGate.push(chunk) : [chunk];
            for (const frame of frames) ws.send(frame);
          } catch {
            stoppedForBackpressure = true;
            nextCapture.stop();
            if (capture.current === nextCapture) capture.current = null;
            finishSpeech.current = null;
            setAudioAvailable(false);
            setActiveActionLabel("Microphone stream paused. Try reconnecting.");
          }
        },
        () => {
          if (ws.readyState !== WebSocket.OPEN) return;
          ws.send(JSON.stringify({ type: "set_language", language: languageRef.current }));
          ws.send(JSON.stringify({ type: "audio_start", sample_rate: 16_000, encoding: "linear16" }));
          audioSessionStarted = true;
        },
        mode === "openai" || mode === "hybrid"
          ? {
              onSpeechStart: () => {
                manuallyCommitted = false;
                voiceTurnEndedAt.current = null;
                answerAudioOriginAt.current = null;
                voiceTimingOrigin.current = null;
                setVoiceFailureStage(null);
                setTranscriptFinalized(false);
                setSubtitles("");
                setCanReplayResponse(false);
                audioOutputUnavailableRef.current = false;
                setAudioOutputUnavailable(false);
                responses.current.interrupt();
                playback.current.stop();
                setVoicePhase("listening");
                setActiveActionLabel("Listening to your voice");
                if (ws.readyState === WebSocket.OPEN) {
                  ws.send(JSON.stringify({ type: "audio_turn_start" }));
                  if (mode === "openai") {
                    for (const frame of inputGate.start()) ws.send(frame);
                  }
                }
              },
              onSpeechEnd: () => {
                inputGate.end();
                if (manuallyCommitted) {
                  manuallyCommitted = false;
                  return;
                }
                voiceTurnEndedAt.current = performance.now();
                answerAudioOriginAt.current = voiceTurnEndedAt.current;
                voiceTimingOrigin.current = "voice";
                voicePhaseRef.current = "transcribing";
                setVoicePhase("transcribing");
                setActiveActionLabel("Working on your request…");
                if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "audio_turn_end" }));
              },
              onLevel: (rms, frameMs) => {
                if (inputSignalSeen) return;
                if (rms >= 0.0001) {
                  inputSignalSeen = true;
                  setMicrophoneSignal("detected");
                } else {
                  silentInputMs += frameMs;
                  if (silentInputMs >= 4_000 && silentInputMs - frameMs < 4_000) {
                    setMicrophoneSignal("silent");
                    setActiveActionLabel("No microphone sound yet. Check your input device.");
                  }
                }
              },
              onCaptureStalled: () => {
                if (capture.current !== nextCapture) return;
                capture.current = null;
                finishSpeech.current = null;
                setAudioAvailable(false);
                setAudioAnalyser(null);
                setVoiceFailureStage("microphone");
                setVoicePhase("error");
                setActiveActionLabel("Microphone stopped. Reconnect to continue.");
                if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "audio_end" }));
              },
            }
          : undefined,
        selectedInputRef.current,
      );
      if (ws.readyState !== WebSocket.OPEN || capture.current !== nextCapture) {
        nextCapture.stop();
        if (capture.current === nextCapture) capture.current = null;
        finishSpeech.current = null;
        setAudioAnalyser(null);
        return;
      }
      setAudioAnalyser(nextCapture.getAnalyser());
      if (!firstCaptureFrameSeen && voiceFailureStageRef.current === null) {
        setVoicePhase("starting_microphone");
        setActiveActionLabel("Starting microphone…");
      }
      void navigator.mediaDevices.enumerateDevices()
        .then((devices) => setAudioInputs(devices.filter((device) => device.kind === "audioinput")))
        .catch(() => undefined);
    } catch (error: unknown) {
      nextCapture.stop();
      if (capture.current === nextCapture) capture.current = null;
      finishSpeech.current = null;
      if (audioSessionStarted && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "audio_end" }));
      }
      setAudioAvailable(false);
      setAudioAnalyser(null);
      setVoiceFailureStage("microphone");
      setVoicePhase("error");
      setActiveActionLabel(microphoneFailureMessage(error));
    }
  }

  function changeInputDevice(deviceId: string) {
    selectedInputRef.current = deviceId;
    setSelectedInputId(deviceId);
    if (socket?.readyState !== WebSocket.OPEN || !capture.current) return;
    capture.current.stop();
    capture.current = null;
    finishSpeech.current = null;
    setAudioAvailable(false);
    void startCapture(socket, voiceModeRef.current);
  }

  async function connect(force = false, automaticReconnect = false) {
    if (!automaticReconnect) {
      sessionRequestedRef.current = true;
      reconnectAttemptRef.current = 0;
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    }
    if (connecting || (connected && !force)) return;
    setShowDrawer(true);
    setConnecting(true);
    setVoiceFailureStage(null);
    setTranscriptFinalized(false);
    setVoicePhase("connecting");
    setActiveActionLabel("Connecting to the voice service…");
    void playback.current.activate().catch(() => undefined);
    try {
      const sessionResponse = await fetch(`${apiUrl}/v1/voice/session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: voiceModeRef.current }),
      });
      if (!sessionResponse.ok) {
        const errJson = await sessionResponse.json().catch(() => ({}));
        throw new Error(errJson.detail ?? `Voice session failed (${sessionResponse.status})`);
      }
      const session = await sessionResponse.json();
      if (!session || typeof session.ticket !== "string") {
        throw new Error("Invalid voice session from server");
      }
      responses.current.reset();
      sttRestarts.current = 0;
      setLiveTranscript("");
      setSubtitles("");
      setCanReplayResponse(false);
      setTranscriptFinalized(false);
      const ws = new WebSocket(wsUrl);
      ws.binaryType = "arraybuffer";
      ws.onopen = () => {
        setConnecting(false);
        setVoicePhase("authenticating");
        setActiveActionLabel("Securing your voice session…");
        ws.send(JSON.stringify({
          type: "authenticate",
          ticket: session.ticket,
          language: languageRef.current,
        }));
        ws.send(JSON.stringify({ type: "set_language", language: languageRef.current }));
        const hasConsentedContact =
          appointmentForm.consent &&
          appointmentForm.client_name.trim().length >= 2 &&
          appointmentForm.contact_email.trim().length > 3;
        ws.send(
          JSON.stringify({
            type: "booking_contact",
            contact: hasConsentedContact
              ? {
                  client_name: appointmentForm.client_name.trim(),
                  contact_email: appointmentForm.contact_email.trim(),
                  contact_phone: appointmentForm.contact_phone.trim() || null,
                  consent: true,
                }
              : null,
          })
        );
        setActiveActionLabel("Connected. Listening is starting…");
      };
      ws.onclose = (event) => {
        if (event.code !== 1000) {
          console.warn("Voice WebSocket closed", {
            code: event.code, reason: event.reason, wasClean: event.wasClean, url: wsUrl,
          });
        }
        setConnecting(false);
        capture.current?.stop();
        capture.current = null;
        finishSpeech.current = null;
        setSocket(null);
        setAudioAvailable(false);
        setMicrophoneSignal("checking");
        if (shouldAutoReconnectVoice(event.code, sessionRequestedRef.current, reconnectAttemptRef.current)) {
          reconnectAttemptRef.current += 1;
          const attempt = reconnectAttemptRef.current;
          const delay = voiceReconnectDelayMs(attempt);
          setVoiceFailureStage(null);
          setVoicePhase("connecting");
          setActiveActionLabel(`Voice connection interrupted. Reconnecting (${attempt}/3)…`);
          reconnectTimerRef.current = window.setTimeout(() => {
            reconnectTimerRef.current = null;
            if (sessionRequestedRef.current) void connect(true, true);
          }, delay);
          return;
        }
        sessionRequestedRef.current = false;
        if (event.code === 1013) {
          setVoiceFailureStage("session");
          setVoicePhase("error");
          setActiveActionLabel(event.reason || "Voice service is busy. Please retry shortly.");
        } else if (event.code === 1008) {
          setVoiceFailureStage("session");
          setVoicePhase("error");
          setActiveActionLabel(event.reason ? `Voice session rejected: ${event.reason}` : "Voice session authentication failed.");
        } else if (event.code !== 1000) {
          setVoiceFailureStage("session");
          setVoicePhase("error");
          setActiveActionLabel(event.reason ? `Voice connection lost: ${event.reason}` : `Voice connection lost (${event.code}). Check the service and network.`);
        } else {
          setVoicePhase("idle");
          setActiveActionLabel("Voice session ended");
        }
      };
      ws.onerror = () => {
        setConnecting(false);
        setVoiceFailureStage("session");
        setVoicePhase("error");
        setActiveActionLabel(`Could not reach the voice service at ${new URL(wsUrl).host}.`);
      };
      ws.onmessage = (messageEvent) => {
        const raw: unknown = messageEvent.data;
        if (typeof raw !== "string") return;
        const event = parseServerEvent(raw);
        if (!event || !responses.current.accept(event)) return;
        if (shouldInterruptPlayback(event)) playback.current.stop();
        if (event.type === "state" && event.state) {
          const nextPhase = (event.state === "processing" ? "thinking" : event.state) as VoicePhase;
          if (event.interrupt_playback || nextPhase === "thinking") {
            setVoiceFailureStage(null);
            setAudioUnavailableReason(undefined);
            setTranscriptFinalized(false);
            setLiveTranscript("");
            setSubtitles("");
            setCanReplayResponse(false);
            audioOutputUnavailableRef.current = false;
            setAudioOutputUnavailable(false);
          }
          serverPhase.current = nextPhase;
          const waitingForFinalTranscript = voicePhaseRef.current === "transcribing";
          if (!waitingForFinalTranscript && shouldApplyServerVoicePhase(
            nextPhase,
            voiceFailureStageRef.current,
            audioAvailableRef.current,
          )) {
            if (nextPhase === "thinking" && playback.current.isActive) setVoicePhase("speaking");
            else if (nextPhase !== "listening" || !playback.current.isActive) setVoicePhase(nextPhase);
          } else if (!waitingForFinalTranscript && (
            nextPhase === "listening"
            && voiceFailureStageRef.current === null
            && !audioAvailableRef.current
          )) {
            setVoicePhase("starting_microphone");
            setActiveActionLabel("Starting microphone…");
          }
          if (
            !waitingForFinalTranscript
            &&
            nextPhase === "listening"
            && !audioOutputUnavailableRef.current
            && voiceFailureStageRef.current === null
            && audioAvailableRef.current
          ) setActiveActionLabel("Listening for your request");
          if (typeof event.audio_input_available === "boolean") {
            if (
              event.audio_input_available
              && !capture.current
              && voiceFailureStageRef.current === null
            ) void startCapture(ws, voiceModeRef.current);
          }
        }
        if (event.type === "transcript" && !event.is_final && event.text) {
          setLiveTranscript(event.text);
          setActiveActionLabel(`Hearing: ${event.text.slice(-120)}`);
        }
        if (event.type === "transcript" && event.is_final && event.speech_final && event.text) {
          sttRestarts.current = 0;
          setLiveTranscript(event.text);
          setTranscriptFinalized(true);
          setShowDrawer(true);
          voicePhaseRef.current = playback.current.isActive ? "speaking" : "thinking";
          setVoicePhase(playback.current.isActive ? "speaking" : "thinking");
          setAgentDecisionLatencyMs(null);
          setSubstantiveAnswerLatencyMs(null);
          setActiveActionLabel(`You said: “${event.text}”`);
          setMessages((current) => [...current, { role: "customer", text: event.text ?? "", time: stamp() }]);
        }
        if (event.type === "agent_response" && event.decision) {
          const reasoningStatus = parseStructuredReasoningStatus(event);
          if (reasoningStatus) setReasoningProviderStatus(reasoningStatus);
          if (event.reasoning_status) {
            setRuntimeReadiness((current) => current
              ? {
                ...current,
                reasoningStatus: event.reasoning_status ?? current.reasoningStatus,
                reasoningFailureCategory: typeof event.reasoning_failure_category === "string"
                  ? event.reasoning_failure_category
                  : current.reasoningFailureCategory,
              }
              : current);
          }
          setVoicePhase(playback.current.isActive ? "speaking" : "thinking");
          const text = event.decision.spoken_text;
          setSubtitles(text);
          setCanReplayResponse(false);
          replayAudio.current.reset();
          audioOutputUnavailableRef.current = false;
          setAudioOutputUnavailable(false);
          setMessages((current) => [...current, { role: "agent", text, time: stamp() }]);
          setConversationFailed(false);
          const transcriptionRecovery = event.decision.reason === "transcription_incomplete";
          if (transcriptionRecovery) {
            answerAudioOriginAt.current = null;
            setSubstantiveAnswerLatencyMs(null);
            setAgentDecisionLatencyMs(null);
            setActiveActionLabel(text || "I didn’t catch the whole request. Please say it again.");
          } else if (typeof event.latency_ms === "number") {
            setAgentDecisionLatencyMs(Math.round(event.latency_ms));
          }
          const ids = event.decision.property_ids ?? [];
          if (ids.length > 0) {
            setActiveActionLabel(`Found ${ids.length} available ${ids.length === 1 ? "property" : "properties"}`);
            setMatches(ids);
            if (!selectedPropertyId) setSelectedPropertyId(ids[0]);
            loadMatchedProperties(ids);
          } else if (!transcriptionRecovery) {
            setActiveActionLabel("Preparing your spoken reply…");
          }
          if (Array.isArray(event.decision.actions) && event.decision.actions.length > 0) {
            dispatchDecisionActions(event.decision.actions);
          }
        }
        if (event.type === "transcript_low_confidence") {
          playback.current.finish();
          setLiveTranscript(event.text ?? "");
          setVoicePhase("listening");
          setActiveActionLabel("I didn’t hear that clearly. Please say it again.");
        }
        if (event.type === "agent_unavailable") {
          playback.current.finish();
          setVoiceFailureStage("agent");
          setVoicePhase("error");
          setActiveActionLabel("I could not finish that response. Please try again.");
        }
        if (event.type === "stt_unavailable") {
          playback.current.finish();
          if (event.restart_required && event.recoverable && sttRestarts.current < 2 && capture.current) {
            sttRestarts.current += 1;
            setActiveActionLabel("Reconnecting speech recognition. Please repeat.");
            window.setTimeout(() => {
              if (ws.readyState === WebSocket.OPEN && capture.current) {
                ws.send(JSON.stringify({ type: "audio_start", sample_rate: 16_000, encoding: "linear16" }));
              }
            }, sttRestarts.current * 500);
          } else {
            capture.current?.stop();
            capture.current = null;
            finishSpeech.current = null;
            setAudioAvailable(false);
            setVoiceFailureStage("transcription");
            setVoicePhase("error");
            setActiveActionLabel(resolveSttUnavailableMessage(event.reason));
          }
        }
        if (event.type === "audio_unavailable") {
          playback.current.finish();
          audioOutputUnavailableRef.current = true;
          setAudioOutputUnavailable(true);
          setVoiceFailureStage("playback");
          setAudioUnavailableReason(event.reason);
          setActiveActionLabel(resolveAudioUnavailableMessage(event.reason));
        }
        if (event.type === "appointment_result") {
          setAppointmentTone("pending");
          const actionLabel = event.action === "cancellation" ? "CANCELLATION REQUESTED"
            : event.action === "reschedule" ? "RESCHEDULE REQUESTED" : "VISIT REQUESTED";
          const msg = `${actionLabel}: REF ${event.reference ?? ""} — CALENDAR/EMAIL PENDING`;
          setAppointmentStatus(msg);
          setShowDrawer(true);
          setActiveActionLabel(msg);
        }
        if (event.type === "audio_chunk") {
          if (event.acknowledgement) acknowledgementAudioPending.current = true;
          if (event.audio_base64 && !event.acknowledgement && answerAudioOriginAt.current !== null) {
            setSubstantiveAnswerLatencyMs(
              Math.round(performance.now() - answerAudioOriginAt.current),
            );
            answerAudioOriginAt.current = null;
          }
          if (event.encoding && event.sample_rate) {
            replayAudio.current.append({
              audio: event.audio_base64 ?? "",
              encoding: event.encoding as "pcm_s16le" | "audio/mpeg",
              sampleRate: event.sample_rate,
              isFinal: event.is_final ?? false,
            });
          }
          if (event.encoding === "audio/mpeg") playback.current.enqueueEncoded(event.audio_base64 ?? "", event.is_final ?? false);
          else if (event.audio_base64 && event.sample_rate) playback.current.playPcm16(event.audio_base64, event.sample_rate);
          if (event.is_final) {
            if (event.encoding !== "audio/mpeg") playback.current.finish();
            setCanReplayResponse(replayAudio.current.canReplay);
          }
        }
      };
      setSocket(ws);
    } catch (err: unknown) {
      setConnecting(false);
      setVoiceFailureStage("session");
      setVoicePhase("error");
      const msg = err instanceof Error ? err.message : "Failed to connect";
      setActiveActionLabel(msg);
    }
  }

  function unlockAudio() {
    void playback.current.activate().catch(() => undefined);
  }

  async function copyConversation() {
    const transcript = messages
      .map((message) => `${message.role === "agent" ? "Awaaz Estate" : "You"} (${message.time})\n${message.text}`)
      .join("\n\n");
    try {
      await navigator.clipboard.writeText(transcript);
      setConversationCopyStatus("Conversation copied");
    } catch {
      setConversationCopyStatus("Could not copy. Check browser clipboard permission.");
    }
  }

  async function replayLastResponse() {
    const chunks = replayAudio.current.snapshot();
    if (chunks.length === 0) return;
    playback.current.stop();
    try {
      await playback.current.activate();
      enqueueReplay(chunks, playback.current);
    } catch (error: unknown) {
      setVoiceFailureStage("playback");
      setVoicePhase("error");
      setActiveActionLabel(error instanceof Error ? error.message : "Could not replay the voice response");
    }
  }

  function handleCallToggle() {
    if (connected) {
      disconnect();
    } else {
      handleVoiceToggle();
    }
  }

  function handleVoiceToggle() {
    unlockAudio();
    if (connected) {
      disconnect();
    } else if (resolveLiveVoiceAction(runtimeReadiness === null && !readinessCheckFailed ? null : voiceReady) === "connect") {
      void connect();
    } else {
      setVoicePhase("blocked");
      setActiveActionLabel(resolveVoiceNotReadyMessage(voiceModeRef.current));
    }
  }

  function disconnect() {
    sessionRequestedRef.current = false;
    reconnectAttemptRef.current = 0;
    if (reconnectTimerRef.current !== null) {
      window.clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    finishSpeech.current = null;
    voiceTurnEndedAt.current = null;
    answerAudioOriginAt.current = null;
    voiceTimingOrigin.current = null;
    capture.current?.stop();
    capture.current = null;
    playback.current.stop();
    httpTurnAbort.current?.abort();
    httpTurnAbort.current = null;
    setAudioAnalyser(null);
    closeVoiceSession(socket);
    setSocket(null);
    setAudioAvailable(false);
    setMicrophoneSignal("checking");
    setVoiceFailureStage(null);
    setTranscriptFinalized(false);
    setAudioOutputUnavailable(false);
    audioOutputUnavailableRef.current = false;
    setVoicePhase("idle");
    setActiveActionLabel("Voice call disconnected");
  }

  function retryVoiceFailure() {
    if (!voiceReady) {
      setVoiceFailureStage(null);
      setVoicePhase("blocked");
      setActiveActionLabel(resolveVoiceNotReadyMessage(voiceModeRef.current));
      return;
    }
    if (voiceFailureStage === "microphone" && socket?.readyState === WebSocket.OPEN) {
      setVoiceFailureStage(null);
      void startCapture(socket, voiceModeRef.current);
      return;
    }
    if (voiceFailureStage === "playback" && canReplayResponse) {
      setVoiceFailureStage(null);
      void replayLastResponse();
      return;
    }
    if (connected) disconnect();
    setVoiceFailureStage(null);
    void connect(true);
  }

  async function performAction(queryText: string, actionLabel: string) {
    unlockAudio();
    setActiveActionLabel(actionLabel);
    setShowDrawer(true);
    await send(queryText);
  }

  async function send(overrideText?: string) {
    const text = (overrideText ?? input).trim();
    if (!text) return;
    setInput("");
    lastSubmittedText.current = text;
    setConversationFailed(false);
    setShowDrawer(true);
    responses.current.interrupt();
    playback.current.stop();
    unlockAudio();
    setMessages((current) => [...current, { role: "customer", text, time: stamp() }]);
    setVoicePhase("thinking");
    setActiveActionLabel("Working on your message…");

    // If WebSocket is active, send via real-time socket
    if (socket && socket.readyState === WebSocket.OPEN) {
      httpTurnAbort.current?.abort();
      httpTurnAbort.current = null;
      voiceTurnEndedAt.current = performance.now();
      answerAudioOriginAt.current = voiceTurnEndedAt.current;
      voiceTimingOrigin.current = "text";
      socket.send(JSON.stringify({ type: "barge_in" }));
      socket.send(JSON.stringify({ type: "user_text", text, language }));
      return;
    }

    // Without an active voice socket, send this turn to the live AI endpoint.
    const start = performance.now();
    httpTurnAbort.current?.abort();
    const controller = new AbortController();
    httpTurnAbort.current = controller;
    try {
      const response = await fetch(`${apiUrl}/v1/conversations/${conversationId.current}/turn`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, language }),
        signal: controller.signal,
      });
      if (httpTurnAbort.current !== controller) return;
      if (!response.ok) throw new Error(`Server returned ${response.status}`);
      const data = await response.json();
      const reasoningStatus = parseStructuredReasoningStatus(data);
      if (reasoningStatus) setReasoningProviderStatus(reasoningStatus);
      setLastTiming({ label: "Text request", milliseconds: Math.round(performance.now() - start) });
      const decision = data.decision || data;
      const rawReply =
        decision.spoken_text ||
        decision.text ||
        data.spoken_text ||
        data.text;
      if (typeof rawReply !== "string" || !rawReply.trim()) throw new Error("The assistant returned an empty reply");
      const reply = rawReply.trim();
      setConversationFailed(false);
      setSubtitles(reply);
      setMessages((current) => [...current, { role: "agent", text: reply, time: stamp() }]);
      setActiveActionLabel("Reply received");
      setVoicePhase("idle");

      const rawIds: unknown = decision.property_ids || data.property_ids || [];
      const ids = Array.isArray(rawIds) ? rawIds.filter((id): id is string => typeof id === "string") : [];
      if (ids.length > 0) {
        setMatches(ids);
        if (!selectedPropertyId) setSelectedPropertyId(ids[0]);
        setShowDrawer(true);
        loadMatchedProperties(ids);
      }
      const rawActions = decision.actions || data.actions;
      if (Array.isArray(rawActions) && rawActions.length > 0) {
        dispatchDecisionActions(rawActions);
      }
    } catch (error: unknown) {
      if (error instanceof Error && error.name === "AbortError") return;
      if (httpTurnAbort.current !== controller) return;
      setVoicePhase("error");
      setConversationFailed(true);
      setActiveActionLabel("The live assistant could not respond. Please try again.");
      setMessages((current) => [
        ...current,
        {
          role: "agent",
          text: "I couldn't reach the live AI service. Please try again in a moment.",
          time: stamp(),
        },
      ]);
    } finally {
      if (httpTurnAbort.current === controller) httpTurnAbort.current = null;
    }
  }

  sendMessageRef.current = send;

  async function bookVisit() {
    if (!appointmentForm.consent) {
      setAppointmentTone("error");
      setAppointmentStatus("Consent is required before sending a visit request.");
      return;
    }
    if (appointmentSlotError) {
      setAppointmentTone("error");
      setAppointmentStatus(appointmentSlotError);
      return;
    }
    if (!viewingEmailVerified || !viewingVerificationToken) {
      setAppointmentTone("error");
      setAppointmentStatus("Verify your email before reserving this viewing.");
      return;
    }
    if (!selectedPropertyId || !canRequestVisit(propertyDetails[selectedPropertyId])) {
      setAppointmentTone("error");
      setAppointmentStatus("Select a loaded, available listing before requesting a visit.");
      setActiveActionLabel("A visit requires an available company listing.");
      return;
    }
    setActiveActionLabel("Sending your visit request…");
    setAppointmentStatus("Saving the viewing reservation…");
    setAppointmentTone("pending");
    try {
      const response = await fetch(`${apiUrl}/v1/public/viewings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_name: appointmentForm.client_name,
          contact_email: appointmentForm.contact_email,
          contact_phone: appointmentForm.contact_phone || null,
          property_id: selectedPropertyId,
          idempotency_key: viewingIdempotencyKey.current,
          starts_at: appointmentForm.starts_at,
          verification_token: viewingVerificationToken,
          consent: true,
          consent_version: "2026-10-03",
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        if (response.status === 409) await refreshViewingSlots(selectedPropertyId);
        throw new Error(data.detail || "Viewing reservation could not be saved.");
      }
      const delivery = data.delivery_status === "pending"
        ? "External confirmation is pending."
        : data.delivery_status === "not_configured" ? "External email or Calendar delivery is not configured." : `External delivery: ${data.delivery_status}.`;
      setAppointmentTone(data.delivery_status === "pending" ? "pending" : "success");
      setAppointmentStatus(`Reservation saved (${data.status}). Reference ${data.reference}. ${delivery}`);
      viewingIdempotencyKey.current = idempotencyKey();
      setShowDrawer(true);
      setActiveActionLabel(`Viewing reservation saved. Reference ${data.reference}.`);
      setMessages((current) => [
        ...current,
        {
          role: "agent",
          text: `Viewing reservation saved for ${propertyDetails[selectedPropertyId]?.title ?? "the selected property"}. Reference: ${data.reference}. ${delivery}`,
          time: stamp(),
        },
      ]);
    } catch (err: unknown) {
      setAppointmentTone("error");
      setAppointmentStatus(err instanceof Error ? err.message : "Booking failed");
      setActiveActionLabel("The visit request could not be submitted.");
    }
  }

  async function submitPropertyInquiry() {
    if (!inquiryPropertyId || !inquiryForm.consent) {
      setInquiryStatus("Consent is required before sending this inquiry.");
      return;
    }
    setInquiryStatus("Saving your inquiry…");
    try {
      const response = await fetch(`${apiUrl}/v1/public/inquiries`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          property_id: inquiryPropertyId,
          request_type: "property",
          client_name: inquiryForm.name.trim(),
          contact_email: inquiryForm.email.trim(),
          contact_phone: null,
          contact_preference: "email",
          message: inquiryForm.message.trim(),
          consent: true,
          consent_version: "2026-10-03",
          idempotency_key: inquiryIdempotencyKey.current,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Your inquiry could not be saved.");
      const delivery = data.delivery_status === "pending" ? "Staff notification is pending." : `Staff notification: ${data.delivery_status}.`;
      setInquiryStatus(`Inquiry saved. ${delivery}`);
      inquiryIdempotencyKey.current = idempotencyKey();
      setMessages((current) => [...current, {
        role: "agent",
        text: `Your property inquiry has been saved. ${delivery}`,
        time: stamp(),
      }]);
    } catch (error) {
      setInquiryStatus(error instanceof Error ? error.message : "Your inquiry could not be saved.");
    }
  }

  function openBookingFor(propertyId: string) {
    const property = propertyDetails[propertyId];
    if (!canRequestVisit(property)) {
      setAppointmentTone("error");
      setAppointmentStatus("This listing is unavailable or its details have not loaded, so a visit cannot be requested.");
      return;
    }
    setSelectedPropertyId(propertyId);
    setAppointmentStatus("");
    setAppointmentTone("info");
    setViewingOtp("");
    setViewingOtpMessage("");
    setViewingEmailVerified(false);
    setViewingVerificationToken("");
    setViewingSlots([]);
    void refreshViewingSlots(propertyId);
    bookingDialog.current?.showModal();
  }

  function dispatchDecisionActions(rawActions: unknown[]) {
    if (!Array.isArray(rawActions) || rawActions.length === 0) return;
    for (const raw of rawActions) {
      if (!raw || typeof raw !== "object") continue;
      const action = raw as {
        id?: string;
        kind: "filter_catalog" | "compare_properties" | "shortlist_property" | "calculate_mortgage" | "schedule_viewing" | "navigate_to";
        payload?: Record<string, unknown>;
        summary?: string;
        executed?: boolean;
      };
      if (!action.kind) continue;
      const payload = action.payload || {};

      // 1. Calculate Mortgage Action
      if (action.kind === "calculate_mortgage") {
        const price = typeof payload.property_price_pkr === "number" ? payload.property_price_pkr : 0;
        if (price <= 0) {
          setActiveActionLabel("I need a property price before opening an installment estimate.");
          continue;
        }
        const down = typeof payload.down_payment_pct === "number" ? payload.down_payment_pct : 25;
        const tenure = typeof payload.tenure_years === "number" ? payload.tenure_years : 15;
        setMortgageCustomProperty({
          id: "CALC",
          title: `Financing Estimate (${formatPricePKR(price)})`,
          city: "Islamabad",
          area: "Capital",
          price_pkr: price,
          available: true,
          bedrooms: 0,
          size_sqft: 0,
          purpose: "sale",
          amenities: [],
          payment_plan: "",
          assigned_employee: "Awaaz Advisory",
          source_version: "1",
          source: "user",
        });
        setMortgageCustomDownPct(down);
        setMortgageCustomTenureYears(tenure);
        setShowMortgageCalc(true);
        setActiveActionLabel(action.summary || "Opened mortgage installment calculator");
      }

      // 2. Shortlist Property Action
      if (action.kind === "shortlist_property") {
        const propId = String(payload.property_id || "").toLowerCase();
        const property = propertyDetails[propId];
        if (!property || !property.available) {
          setActiveActionLabel("I could not save that listing because it is not in the current available results.");
          continue;
        }
        const isAdd = payload.action !== "remove";
        try {
          const raw = window.localStorage.getItem("awaaz_guest_shortlist");
          const list = raw ? JSON.parse(raw) : [];
          const currentList: string[] = Array.isArray(list) ? list : [];
          let updatedList: string[];
          if (isAdd) {
            updatedList = currentList.includes(propId) ? currentList : [propId, ...currentList];
          } else {
            updatedList = currentList.filter((s) => s !== propId);
          }
          window.localStorage.setItem("awaaz_guest_shortlist", JSON.stringify(updatedList));
          window.dispatchEvent(new CustomEvent("awaaz:shortlist:changed", { detail: updatedList }));
        } catch {
          // localStorage might be unavailable in sandboxed context
        }
        setActiveActionLabel(action.summary || `Property ${propId.toUpperCase()} ${isAdd ? "added to" : "removed from"} shortlist`);
      }

      // 3. Navigation Action
      if (action.kind === "navigate_to") {
        const targetPath = String(payload.path || "/properties");
        const label = String(payload.label || "Page");
        setActiveActionLabel(`Navigating to ${label}...`);
        setTimeout(() => {
          if (window.parent === window) {
            window.location.href = targetPath;
          }
        }, 1200);
      }

      // 4. Filter Catalog Action
      if (action.kind === "filter_catalog") {
        const parts = [payload.city, payload.area, payload.purpose].filter(Boolean).map(String);
        setActiveActionLabel(action.summary || `Filtered catalog: ${parts.join(" · ")}`);
      }

      // 5. Schedule Viewing Action
      if (action.kind === "schedule_viewing") {
        const pid = String(payload.property_id || "");
        if (pid) {
          setSelectedPropertyId(pid);
          openBookingFor(pid);
        } else if (selectedPropertyId) {
          openBookingFor(selectedPropertyId);
        }
        setActiveActionLabel(action.summary || "Viewing request form opened. Confirm a slot and your contact consent to submit it.");
      }

      // 6. Compare action
      if (action.kind === "compare_properties") {
        const ids = Array.isArray(payload.property_ids)
          ? payload.property_ids.filter((id): id is string => typeof id === "string" && Boolean(propertyDetails[id]?.available))
          : [];
        if (ids.length < 2) {
          setActiveActionLabel("Search for at least two currently available listings before comparing.");
          continue;
        }
        setComparedPropertyIds(ids.slice(0, 3));
        setShowCompareHUD(true);
        setActiveActionLabel(action.summary || `Comparing ${Math.min(ids.length, 3)} available listings`);
      }

      // Forward action to parent window bridge if present
      const trustedOrigin = bridgeParentOrigin.current;
      if (trustedOrigin && window.parent && window.parent !== window) {
        window.parent.postMessage(
          createActionExecutedMessage({
            id: action.id || `act-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
            kind: action.kind,
            payload,
            summary: action.summary || "",
            executed: action.kind === "schedule_viewing" ? false : action.executed !== false,
          }),
          trustedOrigin
        );
      }
    }
  }

  return (
    <main className={`orbit-platform ${showDrawer ? "has-conversation" : ""}`} aria-label="Awaaz Estate Voice Assistant">
      {/* Top HUD Bar */}
      <header className="orbit-header">
        <div className="orbit-brand">
          <div className="orbit-logo-crest">
            <Icon>{paths.spark}</Icon>
          </div>
          <div className="orbit-title-group">
            <span className="orbit-brand-title">Awaaz Estate</span>
            <span className="orbit-version-badge">PROPERTY CONCIERGE</span>
          </div>
        </div>

        {/* Real-time Action Banner across Orbit Header */}
        <div className="orbit-action-banner">
          <span className={`orbit-action-indicator ${connected ? "live" : ""}`} />
          <span className="orbit-action-text">{activeActionLabel}</span>
        </div>

        <div className="orbit-header-tools">
          <button
            type="button"
            className="orbit-icon-btn"
            onClick={() => setShowSettingsModal(true)}
            title="Audio & Language Settings"
            aria-label="Audio and language settings"
          >
            <Icon>{paths.settings}</Icon>
          </button>

          <div
            className={`orbit-status-chip ${connectionStatus.tone}`}
            title={runtimeReadiness?.voiceVerification === "configuration_only" && voiceReady
              ? `${connectionStatus.label}. ${voiceMode} credentials and SDK are configured; provider connectivity and audio are checked during a live call.`
              : `${connectionStatus.label}. Selected ${voiceMode} voice route ${voiceReady ? "is configured" : "is not configured"}.`}
            aria-label={runtimeReadiness?.voiceVerification === "configuration_only" && voiceReady
              ? `${connectionStatus.label}. Provider connectivity and audio are checked during a live call.`
              : `${connectionStatus.label}. Selected ${voiceMode} voice route ${voiceReady ? "configured" : "not configured"}.`}
            role="status"
            aria-live="polite"
          >
            <span className="status-dot" />
            <span>{connectionStatus.label}</span>
          </div>
        </div>
      </header>

      {appointmentStatus && (
        <div className={`appointment-status-banner tone-${appointmentTone}`} role="status" aria-live="polite">
          <span>{appointmentStatus}</span>
          <button type="button" onClick={() => setAppointmentStatus("")} aria-label="Dismiss appointment status">×</button>
        </div>
      )}

      {/* Voice-first stage: the live conversation and server state remain visible and verifiable. */}
      <div className="orbit-center-stage">
        {/* Voice workspace: the orb reflects live session state; conversation text remains the source of truth. */}
        <div className="orbit-core-view">
          <div className="orbit-canvas-wrap">
            <NeuralOrb
              voicePhase={displayVoicePhase}
              isAudioActive={connected && (displayVoicePhase === "speaking" || displayVoicePhase === "listening")}
              onClick={handleVoiceToggle}
              audioAnalyser={audioAnalyser}
            />
          </div>

          {/* Subtitles & State Indicator directly around Orbit */}
          <div className="orbit-state-overlay">
            <div
              className={`orbit-state-pill phase-${displayVoicePhase}`}
              role={displayVoicePhase === "error" ? undefined : "status"}
              aria-live={displayVoicePhase === "error" ? "off" : "polite"}
              aria-atomic="true"
            >
              {displayVoicePhase === "error" ? activeActionLabel : voicePhaseLabels[displayVoicePhase]}
            </div>
            {!connected && voiceReady && runtimeReadiness?.voiceVerification === "configuration_only" && (
              <p className="voice-verification-note" role="status">
                Provider access is checked when the live voice session starts.
              </p>
            )}
            {(reasoningProviderStatus?.status === "cooldown" || reasoningProviderStatus?.status === "provider_error") && (
              <div className="voice-reasoning-warning" role="status">
                <strong>{reasoningProviderStatus.failureCategory === "rate_limited"
                  ? "OpenAI is rate limiting model requests."
                  : reasoningProviderStatus.failureCategory === "authentication_failed"
                    ? "OpenAI rejected the model credentials."
                    : reasoningProviderStatus.failureCategory === "timeout"
                      ? "OpenAI model requests are timing out."
                      : "OpenAI model reasoning is unavailable."}</strong>
                <span> Voice is using deterministic fallback responses. Check the provider status and account limits.</span>
              </div>
            )}
            {(!voiceReady && runtimeReadiness !== null) || readinessCheckFailed ? (
              <section className="voice-readiness-notice" aria-labelledby="voice-readiness-title">
                <div>
                  <strong id="voice-readiness-title">Voice is unavailable right now</strong>
                  <p>Text chat is still available. Check the setup details or voice settings to resolve this route.</p>
                  {runtimeReadiness && (runtimeReadiness.blockers.length > 0 || Object.values(runtimeReadiness.options).some(Boolean)) && (
                    <details>
                      <summary>{runtimeReadiness.blockers.length > 0 ? "Setup details" : "Available voice routes"}</summary>
                      <ul>
                        {runtimeReadiness.blockers.map((blocker) => <li key={blocker}>{blocker}</li>)}
                        {Object.entries(runtimeReadiness.options).filter(([, available]) => available).map(([route]) => (
                          <li key={route}>{route === "hybrid" ? "UrduLish hybrid" : route === "openai" ? "OpenAI Realtime" : "Standard"} route is configured. Provider connectivity and audio are checked during a live call. Change the conversation language in settings to select its route.</li>
                        ))}
                      </ul>
                    </details>
                  )}
                  {readinessCheckFailed && <p>The backend readiness check did not respond. Confirm the API is running.</p>}
                </div>
                <div className="voice-readiness-actions">
                  <button type="button" onClick={() => {
                    setReadinessCheckFailed(false);
                    setReadinessRefreshKey((current) => current + 1);
                  }}>Check again</button>
                  <button type="button" onClick={() => setShowSettingsModal(true)}>Voice settings</button>
                  <button type="button" onClick={() => textInputRef.current?.focus()}>Use text chat</button>
                </div>
              </section>
            ) : null}
            {(connecting || connected || voiceFailureStage !== null) && (
              <details
                className="voice-diagnostics"
                aria-label="Voice troubleshooting details"
              >
                <summary className="voice-diagnostics-summary">
                  <span>Voice troubleshooting</span>
                  <span className="voice-diagnostics-summary-state">
                    {voiceFailureStage
                      ? `Issue: ${voiceStages.find((stage) => stage.id === voiceFailureStage)?.label ?? voiceFailureStage}`
                      : connected ? "Connection active" : "View connection steps"}
                  </span>
                </summary>
                <ol className="voice-diagnostics-steps">
                  {voiceStages.map((stage, index) => (
                    <li
                      key={stage.id}
                      className={`voice-diagnostic-step state-${stage.state}`}
                      aria-current={stage.state === "active" ? "step" : undefined}
                    >
                      <span className="voice-diagnostic-index">{stage.state === "done" ? "✓" : index + 1}</span>
                      <span className="voice-diagnostic-copy">
                        <strong>{stage.label}</strong>
                        <small>{stage.detail}</small>
                      </span>
                    </li>
                  ))}
                </ol>
                {voiceFailureStage && shouldOfferVoiceRetry(audioUnavailableReason) && (
                  <button type="button" className="voice-diagnostic-retry" onClick={retryVoiceFailure}>
                    {voiceFailureStage === "microphone" ? "Retry microphone"
                      : voiceFailureStage === "playback" && canReplayResponse ? "Replay spoken reply"
                        : "Retry voice connection"}
                  </button>
                )}
              </details>
            )}
            {connected && (liveTranscript || displayVoicePhase === "listening" || displayVoicePhase === "transcribing") && (
              <div className="voice-live-transcript" aria-live="polite" aria-atomic="true">
                <span className="voice-live-transcript-label">
                  <span className="voice-live-transcript-dot" />
                  {liveTranscript ? "LIVE TRANSCRIPT" : displayVoicePhase === "transcribing" ? "TRANSCRIBING" : "YOUR TURN"}
                </span>
                <p>{liveTranscript || (displayVoicePhase === "transcribing" ? "Finishing your request…" : "Speak naturally. I’m listening.")}</p>
              </div>
            )}
            {subtitles && !showDrawer && (
              <p className="orbit-subtitles-stream">"{subtitles}"</p>
            )}
            {displayVoicePhase === "speaking" && (
              <button
                type="button"
                className="barge-in-btn"
                onClick={() => {
                  playback.current.stop();
                  if (socket?.readyState === WebSocket.OPEN) {
                    socket.send(JSON.stringify({ type: "barge_in" }));
                  } else {
                    setVoicePhase(voiceReady ? "idle" : "blocked");
                    setActiveActionLabel("Speech stopped");
                  }
                  if (socket?.readyState === WebSocket.OPEN) {
                    setVoicePhase("listening");
                    setActiveActionLabel("Listening to you");
                  }
                }}
                aria-label="Tap to interrupt agent speech"
              >
                <span className="barge-in-ring" />
                <span>Tap to Interrupt / Barge-In</span>
              </button>
            )}
          </div>

          {/* Audio Waveform Spectrum */}
          <WaveformVisualizer
            mode={connected && displayVoicePhase === "listening"
              ? "listening"
              : connected && displayVoicePhase === "speaking" ? "speaking" : "idle"}
            analyser={audioAnalyser}
          />
        </div>

      </div>

      {/* Floating Bottom Dock (Directly beneath the Orbit) */}
      <div className="orbit-bottom-dock">
        {voiceFailureStage && (
          <div className="voice-error-notice" role="alert" aria-live="assertive">
            <span>{activeActionLabel}</span>
            <a href={`${publicWebsiteOrigin(bridgeParentOrigin.current)}/properties`} target="_top">Browse listings</a>
            {shouldOfferVoiceRetry(audioUnavailableReason) && (
              <button
                type="button"
                onClick={retryVoiceFailure}
                aria-label={voiceFailureStage === "microphone" ? "Retry microphone"
                  : voiceFailureStage === "playback" && canReplayResponse ? "Replay spoken reply"
                    : "Retry voice connection"}
              >
                {voiceFailureStage === "microphone" ? "Retry microphone"
                  : voiceFailureStage === "playback" && canReplayResponse ? "Replay reply"
                    : "Retry voice"}
              </button>
            )}
          </div>
        )}
        <div className="orbit-dock-pill-bar">
          <button
            type="button"
            className={`dock-call-pill ${connected ? "in-call" : ""}`}
            onClick={handleCallToggle}
            disabled={connecting}
            aria-label={connected ? "Stop Voice Chat" : "Start Voice Chat"}
          >
            <Icon>{connected ? paths.phone : paths.mic}</Icon>
            <span>{connecting ? "Connecting…" : connected ? "Stop Voice Chat" : "Start Voice Chat"}</span>
          </button>

          {canReplayResponse && (
            <button
              type="button"
              className="dock-action-pill"
              onClick={() => void replayLastResponse()}
              aria-label="Replay last voice response"
            >
              <Icon>{paths.volume}</Icon>
              <span>Replay reply</span>
            </button>
          )}

          {matches.length >= 2 && (
            <button
              type="button"
              className={`dock-action-pill ${showCompareHUD ? "active" : ""}`}
              onClick={() => {
                if (comparedPropertyIds.length === 0) {
                  setComparedPropertyIds(matches.slice(0, 3));
                }
                setShowCompareHUD(true);
              }}
              aria-label="Compare selected property listings"
            >
              <Icon>{paths.building}</Icon>
              <span>Compare</span>
              {comparedPropertyIds.length > 0 && (
                <span className="dock-count-badge">{comparedPropertyIds.length}</span>
              )}
            </button>
          )}

          <a className="dock-action-pill" href={`${publicWebsiteOrigin(bridgeParentOrigin.current)}/properties`} target="_top" aria-label="Browse company property listings">
            <Icon>{paths.home}</Icon>
            <span>Browse listings</span>
          </a>

          <button
            type="button"
            className={`dock-action-pill ${showMortgageCalc ? "active" : ""}`}
            onClick={() => setShowMortgageCalc(true)}
            aria-label="Open Mortgage and Installment Calculator"
          >
            <Icon>{paths.spark}</Icon>
            <span>Finance</span>
          </button>

          <div className={`dock-asr-pill ${audioAvailable ? "live" : ""}`}>
            <span className="asr-led" />
            <span>Microphone · {audioAvailable
              ? microphoneSignal === "detected" ? "active" : "ready"
              : connected ? "starting" : "off"}</span>
          </div>

          {connected && audioAvailable && displayVoicePhase === "listening" && (
            <button type="button" className="dock-action-pill" onClick={() => finishSpeech.current?.()} aria-label="Finish speaking and get reply">
              <Icon>{paths.send}</Icon>
              <span>Reply now</span>
            </button>
          )}

        </div>

      </div>

      {/* Persistent conversation and recommendations panel */}
      {showDrawer && (
        <aside className="orbit-floating-drawer" aria-label="Conversation and property recommendations">
          <div className="drawer-bar-top">
            <div className="drawer-title-wrap">
              <Icon>{paths.spark}</Icon>
              <span>Conversation & listings ({matches.length})</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              {messages.length > 0 && (
                <button
                  type="button"
                  className="drawer-copy-btn"
                  onClick={() => void copyConversation()}
                  aria-label="Copy conversation transcript"
                  title="Copy conversation"
                >
                  <Icon>{paths.copy}</Icon>
                </button>
              )}
              {matches.length >= 2 && (
                <button
                  type="button"
                  className="drawer-compare-trigger"
                  onClick={() => {
                    if (comparedPropertyIds.length === 0) {
                      setComparedPropertyIds(matches.slice(0, 3));
                    }
                    setShowCompareHUD(true);
                  }}
                  aria-label="Compare properties side-by-side"
                >
                  <Icon>{paths.compare}</Icon>
                  Compare ({comparedPropertyIds.length || Math.min(matches.length, 3)}) Side-by-Side
                </button>
              )}
            </div>
          </div>

          <span className="drawer-copy-status" role="status" aria-live="polite">
            {conversationCopyStatus}
          </span>

          <div className="drawer-scroll-body">
            {/* Messages */}
            <div ref={messageListRef} className="drawer-messages-list" role="log" aria-label="Conversation messages" aria-live="polite" aria-relevant="additions">
              {messages.length === 0 ? (
                <div className="conversation-start-state" role="status">
                  <span className="conversation-start-eyebrow">PROPERTY CONCIERGE</span>
                  <p>Ask, search, compare, or save a property</p>
                  <small>Tell me your city, area, budget, or property type. I can search current listings, save an option, compare results, and open an installment estimate. I’ll ask before submitting a viewing request.</small>
                  <div className="assistant-task-starters" aria-label="Try a property task">
                    <button type="button" onClick={() => void performAction("Find available homes in Islamabad under 5 crore", "Searching available Islamabad homes")}>Homes in Islamabad</button>
                    <button type="button" onClick={() => void performAction("Find available two bedroom apartments in Karachi under 3 crore", "Searching two-bedroom Karachi apartments")}>2-bedroom in Karachi</button>
                    <button type="button" onClick={() => void performAction("What can you do for me?", "Explaining assistant actions")}>What can you do?</button>
                  </div>
                </div>
              ) : messages.map((m, idx) => (
                <div key={`${m.time}-${idx}`} className={`drawer-bubble role-${m.role}`}>
                  <span className="bubble-meta">
                    <strong className="bubble-author">{m.role === "agent" ? "Awaaz Estate" : "You"}</strong>
                    <time className="bubble-time">{m.time}</time>
                  </span>
                  <div className="bubble-text">{m.text}</div>
                </div>
              ))}
            </div>

            {matchMessage && <p className="assistant-match-notice" role="status">{matchMessage}</p>}
            {conversationFailed && (
              <div className="assistant-recovery-panel" role="alert">
                <p>The assistant could not return a response. Retry your question or browse the current catalog.</p>
                <button type="button" onClick={() => void send(lastSubmittedText.current)}>Retry question</button>
                <a href={`${publicWebsiteOrigin(bridgeParentOrigin.current)}/properties`} target="_top">Browse listings</a>
              </div>
            )}
            {matches.length === 0 && (
              <div className="conversation-empty-state" role="status">
                <p>No suggestions yet. Ask for a fresh search or browse the current company listings. Only public listings with current availability can appear here.</p>
                <a className="assistant-listing-link" href={`${publicWebsiteOrigin(bridgeParentOrigin.current)}/properties`} target="_top">Browse company listings</a>
              </div>
            )}

            {/* Properties Cards Grid */}
            {matches.length > 0 && (
              <div className="drawer-properties-grid">
                {matches.map((id) => {
                  const prop = propertyDetails[id];
                  const detailsLoading = loadingPropertyIds.includes(id);
                  const isCompared = comparedPropertyIds.includes(id);
                  const listingHref = prop?.slug ? `${publicWebsiteOrigin(bridgeParentOrigin.current)}/properties/${encodeURIComponent(prop.slug)}` : null;
                  return (
                    <div key={id} className="drawer-property-item">
                      {prop?.photos?.[0] ? (
                        <img className="assistant-property-photo" src={prop.photos[0].url} alt={prop.photos[0].alt_text || `${prop.title} property photo`} loading="lazy" />
                      ) : <div className="assistant-property-no-photo">No public photo is available</div>}
                      <div className="assistant-property-content">
                      <div className="item-head">
                        <span className="prop-id">{prop?.publisher?.name || "Published listing"}</span>
                        <span className="prop-purpose">{prop?.transaction_type?.toUpperCase() ?? (detailsLoading ? "LOADING" : "DETAILS UNAVAILABLE")}</span>
                      </div>
                      <h4 className="prop-title">{prop?.title ?? (detailsLoading ? "Loading current listing…" : "Listing no longer available")}</h4>
                      <div className="prop-geo">{prop ? `${prop.area}, ${prop.city}` : "This result could not be confirmed from the public catalog."}</div>
                      <div className="prop-price">{prop ? `${formatPricePKR(prop.price_pkr)}${prop.transaction_type === "rent" ? ` / ${prop.rental_period || "period not confirmed"}` : ""}` : ""}</div>
                      {prop && (
                        <div className="prop-badges">
                          <span className="unit-badge">{reviewedSizeLabel(prop.size_sqft, prop.sqft_per_marla)}</span>
                          <span className={`availability-badge ${prop.available ? "available" : "unavailable"}`}>
                            {prop.available ? "Availability recently confirmed" : "Ask for current availability"}
                          </span>
                        </div>
                      )}
                      {prop && (
                        <div className="prop-specs">
                          <span>{prop.bedrooms > 0 ? `${prop.bedrooms} bed` : prop.property_type ?? "Commercial"}</span>
                          {prop.bathrooms !== null && prop.bathrooms !== undefined && <><span>·</span><span>{prop.bathrooms} bath</span></>}
                          <span>•</span>
                          <span>{prop.size_sqft.toLocaleString()} sq ft</span>
                        </div>
                      )}
                      {prop?.verification?.status && prop.verification.status !== "not_reviewed" && prop.verification.scope && (
                        <p className="assistant-verification-note">{prop.verification.scope}{prop.verification.reviewed_at ? ` · reviewed ${new Date(prop.verification.reviewed_at).toLocaleDateString("en-PK")}` : ""}</p>
                      )}
                      <div className="prop-actions-row">
                        {listingHref && <a className="assistant-listing-link" href={listingHref} target="_top">Full listing</a>}
                        <button
                          type="button"
                          className={`prop-compare-toggle ${isCompared ? "selected" : ""}`}
                          onClick={() => {
                            setComparedPropertyIds((prev) =>
                              prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
                            );
                          }}
                        >
                          {isCompared ? "✓ Selected" : "+ Compare"}
                        </button>
                        <button
                          type="button"
                          className="prop-book-action"
                          onClick={() => openBookingFor(id)}
                          disabled={!canRequestVisit(prop)}
                        >
                          {canRequestVisit(prop) ? "Request viewing" : "Viewing unavailable"}
                        </button>
                      </div>
                      {prop && <button className="assistant-inquiry-link" type="button" onClick={() => {
                        setInquiryPropertyId(id);
      setInquiryForm({ name: "", email: "", message: "", consent: false });
                        setInquiryStatus("");
                        inquiryDialog.current?.showModal();
                      }}>Ask about this property</button>}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
          <form className="assistant-conversation-composer" onSubmit={(event) => { event.preventDefault(); void send(); }}>
            <label className="sr-only" htmlFor="assistant-message-input">Message Awaaz Estate</label>
            <input id="assistant-message-input" ref={textInputRef} value={input} onChange={(event) => setInput(event.target.value)} maxLength={1000} placeholder="Ask about area, budget, listings, or a viewing…" />
            <button type="submit" aria-label="Send message" disabled={!input.trim()}><Icon>{paths.send}</Icon><span>Send</span></button>
          </form>
        </aside>
      )}

      {/* Settings Modal Dialog */}
      {showSettingsModal && (
        <dialog
          ref={settingsDialog}
          className="orbit-native-modal"
          aria-labelledby="voice-settings-title"
          onCancel={(event) => {
            event.preventDefault();
            setShowSettingsModal(false);
          }}
          onClick={(event) => {
            if (event.target === event.currentTarget) setShowSettingsModal(false);
          }}
        >
          <div className="orbit-modal-window">
            <div className="modal-top">
            <h3 id="voice-settings-title">Voice & Language Settings</h3>
              <button type="button" className="modal-x-btn" onClick={() => setShowSettingsModal(false)} aria-label="Close voice settings">✕</button>
            </div>
            <div className="modal-fields">
              <div className="form-row">
                <label>Voice session route</label>
                <div className="settings-value">
                  {voiceMode === "hybrid"
                    ? language === "en"
                      ? "Deepgram English transcription with the speech provider configured by the server"
                      : "Deepgram Urdu transcription with the speech provider configured by the server"
                    : "OpenAI multilingual transcription with the speech provider configured by the server"}
                </div>
              </div>

              <div className="form-row">
                <label>Voice Language</label>
                <select
                  value={language}
                  onChange={(e) => changeLanguage(e.target.value as typeof language)}
                >
                  <option value="ur-Latn">Urdu (Roman / English alphabet)</option>
                  <option value="ur-Arab">Urdu (اردو رسم الخط)</option>
                  <option value="en">English (Pakistani Real Estate)</option>
                  <option value="hi">Hindi (हिन्दी)</option>
                  <option value="ar">Arabic (العربية)</option>
                  <option value="pa">Punjabi (پنجابی)</option>
                </select>
              </div>

              <div className="form-row">
                <label htmlFor="voice-input-device">Microphone</label>
                <select
                  id="voice-input-device"
                  value={selectedInputId}
                  onChange={(event) => changeInputDevice(event.target.value)}
                >
                  <option value="">System default microphone</option>
                  {audioInputs.filter((device) => device.deviceId).map((device, index) => (
                    <option key={device.deviceId} value={device.deviceId}>
                      {device.label || `Microphone ${index + 1}`}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-row">
                <label>Voice Output</label>
                <div className="settings-value">Generated by the live speech route configured on the backend. Provider outages are reported in the conversation.</div>
              </div>
            </div>
            <p className="settings-change-hint">Language and microphone changes apply immediately. Changing language may reconnect the voice route.</p>
            <div className="modal-foot">
              <button type="button" className="save-btn" onClick={() => setShowSettingsModal(false)}>Done</button>
            </div>
          </div>
        </dialog>
      )}

      {/* Site Visit Booking Modal Dialog */}
      <dialog className="orbit-booking-dialog" ref={bookingDialog} aria-labelledby="booking-title">
        <div className="dialog-top-bar">
          <div className="dialog-title-wrap">
            <Icon>{paths.calendar}</Icon>
          <h2 id="booking-title">Request a site visit</h2>
          </div>
          <button type="button" className="dialog-x" onClick={() => bookingDialog.current?.close()} aria-label="Close dialog">
            <Icon>{paths.close}</Icon>
          </button>
        </div>

        <section className="dialog-body">
          <p className="dialog-info">Choose a current company viewing slot and verify your email. Saving the reservation and delivering a Calendar or email notification are reported separately.</p>
          <div className="dialog-grid">
            <div className="field-block">
              <label>Selected Property</label>
              <select
                aria-label="Select property"
                value={selectedPropertyId}
                onChange={(e) => setSelectedPropertyId(e.target.value)}
                className="dialog-select-input"
              >
                {availableMatches.length > 0 ? (
                  availableMatches.map((id) => (
                    <option key={id} value={id}>
                      {id} — {propertyDetails[id]?.title ?? "Property"} ({propertyDetails[id]?.city ?? ""})
                    </option>
                  ))
                ) : (
                  <option value="" disabled>No loaded available listings</option>
                )}
              </select>
            </div>

            <div className="field-block">
              <label htmlFor="assistant-viewing-slot">Available viewing slot (Pakistan time)</label>
              <select id="assistant-viewing-slot" value={appointmentForm.starts_at} disabled={slotsLoading || viewingSlots.length === 0} onChange={(e) => setAppointmentForm({ ...appointmentForm, starts_at: e.target.value })}>
                <option value="">{slotsLoading ? "Loading available slots…" : "Choose a slot"}</option>
                {viewingSlots.map((slot) => <option key={slot} value={slot}>{new Intl.DateTimeFormat("en-PK", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Karachi" }).format(new Date(slot))} PKT</option>)}
              </select>
              <button type="button" className="assistant-inline-action" onClick={() => selectedPropertyId && void refreshViewingSlots(selectedPropertyId)}>Refresh slots</button>
            </div>

            <div className="field-block">
              <label>Your Full Name</label>
              <input
                aria-label="Your name"
                placeholder="e.g. Armish Iqbal"
                value={appointmentForm.client_name}
                onChange={(e) => setAppointmentForm({ ...appointmentForm, client_name: e.target.value })}
              />
            </div>

            <div className="field-block">
              <label>Email Address</label>
              <input
                aria-label="Email address"
                type="email"
                placeholder="e.g. client@example.com"
                value={appointmentForm.contact_email}
                onChange={(e) => {
                  setAppointmentForm({ ...appointmentForm, contact_email: e.target.value });
                  setViewingEmailVerified(false);
                  setViewingVerificationToken("");
                }}
              />
              <button type="button" className="assistant-inline-action" onClick={() => void requestViewingOtp()} disabled={!appointmentForm.contact_email.trim() || viewingEmailVerified}>Send verification code</button>
              <span className="assistant-inline-status" role="status">{viewingOtpMessage}</span>
              <div className="assistant-otp-row">
                <input aria-label="Email verification code" inputMode="numeric" autoComplete="one-time-code" maxLength={6} placeholder="6-digit code" value={viewingOtp} onChange={(event) => setViewingOtp(event.target.value.replace(/\D/g, "").slice(0, 6))} disabled={viewingEmailVerified} />
                <button type="button" className="assistant-inline-action" onClick={() => void verifyViewingOtp()} disabled={viewingOtp.length !== 6 || viewingEmailVerified}>Verify email</button>
              </div>
            </div>

            <div className="field-block">
              <label>Contact Phone (Optional)</label>
              <input
                aria-label="Phone number"
                type="tel"
                placeholder="e.g. +92 300 1234567"
                value={appointmentForm.contact_phone}
                onChange={(e) => setAppointmentForm({ ...appointmentForm, contact_phone: e.target.value })}
              />
            </div>
            <label className="appointment-consent-field">
              <input
                type="checkbox"
                checked={appointmentForm.consent}
                onChange={(event) => setAppointmentForm({ ...appointmentForm, consent: event.target.checked })}
              />
              <span>I consent to use these contact details to coordinate this visit request.</span>
            </label>
          </div>

          <button
            type="button"
            className="dialog-confirm-action"
            onClick={() => void bookVisit()}
            disabled={!availableMatches.includes(selectedPropertyId) || !appointmentForm.client_name || !viewingEmailVerified || !appointmentForm.consent || Boolean(appointmentSlotError) || appointmentStatus === "Saving the viewing reservation…" || appointmentStatus.startsWith("Reservation saved (")}
          >
            Reserve viewing
          </button>
          {appointmentStatus && <p className={`appointment-note tone-${appointmentTone}`} role="status">{appointmentStatus}</p>}
        </section>
      </dialog>

      <dialog className="orbit-booking-dialog assistant-inquiry-dialog" ref={inquiryDialog} aria-labelledby="assistant-inquiry-title">
        <div className="dialog-top-bar">
          <div className="dialog-title-wrap"><Icon>{paths.home}</Icon><h2 id="assistant-inquiry-title">Ask about this property</h2></div>
          <button type="button" className="dialog-x" onClick={() => inquiryDialog.current?.close()} aria-label="Close inquiry"><Icon>{paths.close}</Icon></button>
        </div>
        <section className="dialog-body">
          <p className="dialog-info">A staff member can follow up using your chosen email. Your contact details are not added to the conversation text.</p>
          <div className="field-block"><label htmlFor="inquiry-name">Your name</label><input id="inquiry-name" value={inquiryForm.name} onChange={(event) => setInquiryForm({ ...inquiryForm, name: event.target.value })} minLength={2} maxLength={100} autoComplete="name" /></div>
          <div className="field-block"><label htmlFor="inquiry-email">Email address</label><input id="inquiry-email" type="email" autoComplete="email" value={inquiryForm.email} onChange={(event) => setInquiryForm({ ...inquiryForm, email: event.target.value })} /></div>
          <div className="field-block"><label htmlFor="inquiry-message">Your question (optional)</label><textarea id="inquiry-message" maxLength={2000} value={inquiryForm.message} onChange={(event) => setInquiryForm({ ...inquiryForm, message: event.target.value })} /></div>
          <label className="appointment-consent-field"><input type="checkbox" checked={inquiryForm.consent} onChange={(event) => setInquiryForm({ ...inquiryForm, consent: event.target.checked })} /><span>I consent to use my contact details to respond to this property inquiry.</span></label>
          <button type="button" className="dialog-confirm-action" onClick={() => void submitPropertyInquiry()} disabled={!inquiryForm.name.trim() || !inquiryForm.email.trim() || !inquiryForm.consent || inquiryStatus === "Saving your inquiry…" || inquiryStatus.startsWith("Inquiry saved.")}>Send inquiry</button>
          {inquiryStatus && <p className="appointment-note" role="status">{inquiryStatus}</p>}
        </section>
      </dialog>

      {/* Side-by-Side Property Comparison HUD */}
      {showCompareHUD && (
        <PropertyComparisonHUD
          properties={
            (comparedPropertyIds.length > 0
              ? comparedPropertyIds
              : matches.slice(0, 3)
            )
              .map((id) => propertyDetails[id])
              .filter((p): p is Property => Boolean(p))
          }
          onClose={() => setShowCompareHUD(false)}
          onBook={(propId) => {
            setShowCompareHUD(false);
            openBookingFor(propId);
          }}
        />
      )}

      {/* Mortgage & Financing Calculator Modal */}
      {showMortgageCalc && (
        <MortgageCalculatorModal
          property={mortgageCustomProperty || propertyDetails[selectedPropertyId] || null}
          initialDownPaymentPct={mortgageCustomDownPct}
          initialTenureYears={mortgageCustomTenureYears}
          onClose={() => {
            setShowMortgageCalc(false);
            setMortgageCustomProperty(null);
            setMortgageCustomDownPct(undefined);
            setMortgageCustomTenureYears(undefined);
          }}
          onBookConsultation={(id) => {
            setShowMortgageCalc(false);
            if (id) openBookingFor(id);
            else bookingDialog.current?.showModal();
          }}
        />
      )}
    </main>
  );
}

const rootElement = document.getElementById("root");
const existingRoot = import.meta.hot?.data.root as Root | undefined;
const root = rootElement ? existingRoot ?? createRoot(rootElement) : undefined;
if (rootElement && root) {
  if (import.meta.hot) import.meta.hot.data.root = root;
  root.render(<App />);
}
