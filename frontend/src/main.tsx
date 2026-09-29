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
  type RuntimeReadiness,
  resolveSttUnavailableMessage,
  resolveVoiceNotReadyMessage,
  resolveVoiceConnectionStatus,
  shouldApplyServerVoicePhase,
  shouldOfferVoiceRetry,
} from "./voiceUiState.mjs";
import { PropertyComparisonHUD } from "./PropertyComparisonHUD";
import { PropertyLocations } from "./PropertyLocations";
import { MortgageCalculatorModal } from "./MortgageCalculatorModal";
import { AnalyticsPanel } from "./AnalyticsPanel";
import { availabilityLabel, canRequestVisit, inventorySourceLabel, inventoryStatusSummary } from "./propertyFacts.mjs";
import { defaultVisitSlot, visitSlotError, visitSlotToIso } from "./visitSlots.mjs";
import { useNativeDialog } from "./useNativeDialog";
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
};

type Message = { role: "customer" | "agent"; text: string; time: string };
type VoicePhase = "checking" | "blocked" | "idle" | "connecting" | "authenticating" | "starting_microphone" | "listening" | "thinking" | "speaking" | "error";
type VoiceFailureStage = "session" | "microphone" | "transcription" | "agent" | "playback";
type FeedbackTone = "info" | "pending" | "success" | "error";
type VoiceMode = "standard" | "openai" | "hybrid";
type InventoryLoadState = "loading" | "ready" | "error";

const stamp = () => new Intl.DateTimeFormat("en-PK", { hour: "numeric", minute: "2-digit" }).format(new Date());

function getMarlaEquivalent(sqft: number): string {
  if (sqft >= 4500) {
    const kanal = (sqft / 4500).toFixed(1).replace(/\.0$/, "");
    return `${kanal} Kanal`;
  }
  const marla = (sqft / 225).toFixed(1).replace(/\.0$/, "");
  return `${marla} Marla`;
}

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

const rawApiUrl = (import.meta.env.VITE_API_URL as string | undefined) || resolveDefaultApiUrl();
const apiUrl = rawApiUrl.replace(/\/+$/, "");
const wsUrl = (import.meta.env.VITE_WS_URL as string | undefined) || (apiUrl.replace(/^http/, "ws") + "/v1/voice");

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
  const voiceFailureStageRef = useRef<VoiceFailureStage | null>(null);
  const [voiceFailureStage, setVoiceFailureStageState] = useState<VoiceFailureStage | null>(null);
  const setVoiceFailureStage = (stage: VoiceFailureStage | null) => {
    voiceFailureStageRef.current = stage;
    setVoiceFailureStageState(stage);
  };
  const [transcriptFinalized, setTranscriptFinalized] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationCopyStatus, setConversationCopyStatus] = useState("");
  const [matches, setMatches] = useState<string[]>([]);
  const [inventoryProperties, setInventoryProperties] = useState<Property[]>([]);
  const [inventoryLoadState, setInventoryLoadState] = useState<InventoryLoadState>("loading");
  const [inventoryRefreshKey, setInventoryRefreshKey] = useState(0);
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
  const [readinessCheckFailed, setReadinessCheckFailed] = useState(false);
  const [readinessRefreshKey, setReadinessRefreshKey] = useState(0);
  const [selectedPropertyId, setSelectedPropertyId] = useState<string>("");
  const [showDrawer, setShowDrawer] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [showAnalytics, setShowAnalytics] = useState(false);
  const [comparedPropertyIds, setComparedPropertyIds] = useState<string[]>([]);
  const [showCompareHUD, setShowCompareHUD] = useState(false);
  const [showLocations, setShowLocations] = useState(false);
  const [showMortgageCalc, setShowMortgageCalc] = useState(false);
  const [lastTiming, setLastTiming] = useState<{ label: string; milliseconds: number } | null>(null);
  const [agentDecisionLatencyMs, setAgentDecisionLatencyMs] = useState<number | null>(null);
  const [substantiveAnswerLatencyMs, setSubstantiveAnswerLatencyMs] = useState<number | null>(null);
  const [audioAnalyser, setAudioAnalyser] = useState<AnalyserNode | null>(null);
  const httpTurnAbort = useRef<AbortController | null>(null);

  const [appointmentForm, setAppointmentForm] = useState({
    client_name: "",
    contact_email: "",
    contact_phone: "",
    starts_at: defaultVisitSlot(),
    consent: false,
  });

  const conversationId = useRef(
    typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `conv-${Date.now()}`
  );
  const bookingDialog = useRef<HTMLDialogElement | null>(null);
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
  const chatBottomRef = useRef<HTMLDivElement | null>(null);

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
      state: transcriptFinalized ? "done" : voiceFailureStage === "transcription" ? "failed" : audioAvailable ? "active" : "waiting",
      detail: transcriptFinalized ? "Recognized" : voiceFailureStage === "transcription" ? "Recognition failed" : audioAvailable ? "Waiting for speech" : "Waiting",
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
  const hasAvailableListings = inventoryProperties.some((property) => canRequestVisit(property));
  const inventoryStatus = inventoryStatusSummary(inventoryLoadState, inventoryProperties);
  const compactInventoryLabel = inventoryStatus.tone === "ready"
    ? `${inventoryProperties.filter(canRequestVisit).length} live`
    : inventoryStatus.tone === "loading" ? "Loading"
      : inventoryStatus.tone === "error" ? "Offline" : "0 listings";
  const appointmentSlotError = visitSlotError(appointmentForm.starts_at);

  useEffect(() => {
    voiceModeRef.current = voiceMode;
  }, [voiceMode]);

  useEffect(() => {
    if (!reconnectAfterLanguageChange.current || socket || connecting) return;
    reconnectAfterLanguageChange.current = false;
    void connect();
  }, [connecting, socket, voiceMode]);

  useEffect(() => {
    if (!showDrawer || (messages.length === 0 && matches.length === 0)) return;
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, matches, showDrawer]);

  // Load properties preview
  useEffect(() => {
    void fetch(`${apiUrl}/v1/properties`)
      .then((res) => {
        if (!res.ok) throw new Error(`Inventory request failed (${res.status})`);
        return res.json();
      })
      .then((data: Property[]) => {
        if (!Array.isArray(data)) throw new Error("Inventory response was not a list");
        setInventoryProperties(data);
        setInventoryLoadState("ready");
      })
      .catch(() => setInventoryLoadState("error"));
  }, [inventoryRefreshKey]);

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
        const configured = readiness.providers[readinessKey] === true;
        setReadinessCheckFailed(false);
        setRuntimeReadiness(readiness);
        setVoicePhase((current) =>
          ["connecting", "authenticating", "listening", "thinking", "speaking", "error"].includes(current)
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
    setLoadingPropertyIds((current) => [...new Set([...current, ...ids])]);
    void Promise.all(ids.map(async (id) => {
      try {
        const response = await fetch(`${apiUrl}/v1/properties/${encodeURIComponent(id)}`);
        if (!response.ok) return null;
        return await response.json() as Property;
      } catch {
        return null;
      }
    })).then((items) => {
      setPropertyDetails((current) => ({
        ...current,
        ...Object.fromEntries(items.filter((item): item is Property => item !== null).map((item) => [item.id, item])),
      }));
    }).finally(() => {
      setLoadingPropertyIds((current) => current.filter((id) => !ids.includes(id)));
    });
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
          if (shouldApplyServerVoicePhase(
            nextPhase,
            voiceFailureStageRef.current,
            audioAvailableRef.current,
          )) {
            if (nextPhase === "thinking" && playback.current.isActive) setVoicePhase("speaking");
            else if (nextPhase !== "listening" || !playback.current.isActive) setVoicePhase(nextPhase);
          } else if (
            nextPhase === "listening"
            && voiceFailureStageRef.current === null
            && !audioAvailableRef.current
          ) {
            setVoicePhase("starting_microphone");
            setActiveActionLabel("Starting microphone…");
          }
          if (
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
          setVoicePhase(playback.current.isActive ? "speaking" : "thinking");
          setAgentDecisionLatencyMs(null);
          setSubstantiveAnswerLatencyMs(null);
          setActiveActionLabel(`You said: “${event.text}”`);
          setMessages((current) => [...current, { role: "customer", text: event.text ?? "", time: stamp() }]);
        }
        if (event.type === "agent_response" && event.decision) {
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
      setLastTiming({ label: "Text request", milliseconds: Math.round(performance.now() - start) });
      const decision = data.decision || data;
      const reply =
        decision.spoken_text ||
        decision.text ||
        data.spoken_text ||
        data.text ||
        "Main aapki madad kar sakta hoon.";
      setSubtitles(reply);
      setMessages((current) => [...current, { role: "agent", text: reply, time: stamp() }]);
      setActiveActionLabel("Reply received");
      setVoicePhase("idle");

      const ids: string[] = decision.property_ids || data.property_ids || [];
      if (ids.length > 0) {
        setMatches(ids);
        if (!selectedPropertyId) setSelectedPropertyId(ids[0]);
        setShowDrawer(true);
        loadMatchedProperties(ids);
      }
    } catch (error: unknown) {
      if (error instanceof Error && error.name === "AbortError") return;
      if (httpTurnAbort.current !== controller) return;
      setVoicePhase("error");
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
    if (!selectedPropertyId || !canRequestVisit(propertyDetails[selectedPropertyId])) {
      setAppointmentTone("error");
      setAppointmentStatus("Select a loaded, available listing before requesting a visit.");
      setActiveActionLabel("A visit requires an available company listing.");
      return;
    }
    setActiveActionLabel("Sending your visit request…");
    setAppointmentStatus("Scheduling site visit…");
    setAppointmentTone("pending");
    try {
      const response = await fetch(`${apiUrl}/v1/appointments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_name: appointmentForm.client_name,
          contact_email: appointmentForm.contact_email,
          contact_phone: appointmentForm.contact_phone || null,
          property_id: selectedPropertyId,
          employee: propertyDetails[selectedPropertyId]?.assigned_employee ?? "",
          idempotency_key:
            typeof crypto !== "undefined" && crypto.randomUUID
              ? crypto.randomUUID()
              : "00000000-0000-0000-0000-000000000001",
          starts_at: visitSlotToIso(appointmentForm.starts_at),
          consent: true,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Booking failed");
      setAppointmentTone("pending");
      setAppointmentStatus(`Visit request recorded. Calendar confirmation pending — reference ${data.reference}.`);
      setShowDrawer(true);
      bookingDialog.current?.close();
      setActiveActionLabel(`Visit request recorded. Reference ${data.reference}.`);
      setMessages((current) => [
        ...current,
        {
          role: "agent",
          text: `Visit request recorded for property ${data.property_id || selectedPropertyId}. Calendar confirmation is pending. Reference: ${data.reference}`,
          time: stamp(),
        },
      ]);
    } catch (err: unknown) {
      setAppointmentTone("error");
      setAppointmentStatus(err instanceof Error ? err.message : "Booking failed");
      setActiveActionLabel("The visit request could not be submitted.");
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
    bookingDialog.current?.showModal();
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
            <span className="orbit-version-badge">VOICE ASSISTANT</span>
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
            onClick={() => setShowAnalytics(true)}
            title="Live service analytics"
            aria-label="Open live service analytics"
          >
            <Icon>{paths.chart}</Icon>
          </button>
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
          <button
            type="button"
            className={`orbit-inventory-chip ${inventoryStatus.tone}`}
            onClick={() => setShowLocations(true)}
            title={`${inventoryStatus.detail}. Open property inventory.`}
            aria-label={`${inventoryStatus.label}. ${inventoryStatus.detail}. Open property inventory.`}
          >
            <Icon>{paths.home}</Icon>
            <span className="orbit-inventory-label" aria-live="polite">{inventoryStatus.label}</span>
            <span className="orbit-inventory-compact" aria-hidden="true">{compactInventoryLabel}</span>
          </button>
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
            {(runtimeReadiness?.reasoningStatus === "cooldown" || runtimeReadiness?.reasoningStatus === "provider_error") && (
              <div className="voice-reasoning-warning" role="status">
                <strong>{runtimeReadiness.reasoningFailureCategory === "rate_limited"
                  ? "OpenAI is rate limiting model requests."
                  : runtimeReadiness.reasoningFailureCategory === "authentication_failed"
                    ? "OpenAI rejected the model credentials."
                    : runtimeReadiness.reasoningFailureCategory === "timeout"
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
            {connected && (liveTranscript || displayVoicePhase === "listening") && (
              <div className="voice-live-transcript" aria-live="polite" aria-atomic="true">
                <span className="voice-live-transcript-label">
                  <span className="voice-live-transcript-dot" />
                  {liveTranscript ? "LIVE TRANSCRIPT" : "YOUR TURN"}
                </span>
                <p>{liveTranscript || "Speak naturally. I’m listening."}</p>
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

          <button
            type="button"
            className={`dock-action-pill ${showDrawer ? "active" : ""}`}
            onClick={() => setShowDrawer(!showDrawer)}
            aria-label="Toggle conversation and property recommendations"
          >
            <Icon>{paths.transcript}</Icon>
            <span>{showDrawer ? "Hide Conversation" : "Conversation"}</span>
            {matches.length > 0 && <span className="dock-count-badge">{matches.length}</span>}
          </button>

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

          <button
            type="button"
            className={`dock-action-pill ${showLocations ? "active" : ""}`}
            onClick={() => setShowLocations(true)}
            aria-label="Browse available property locations"
          >
            <Icon>{paths.home}</Icon>
            <span>Locations</span>
          </button>

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

        {/* Shortcuts submit real questions to the live assistant; they do not use demo inventory. */}
        <div className="orbit-quick-chips-row" role="group" aria-label="Start with a real estate topic">
          {[
            { icon: paths.home, label: "Buy a home", query: "I want to buy a home. Ask for my city, area, and budget, then search available listings." },
            { icon: paths.home, label: "Find a rental", query: "I want to rent a property. Ask for my city, area, and budget, then search available listings." },
            { icon: paths.building, label: "Commercial space", query: "I need a commercial property. Ask for my property type, city, area, and budget." },
            { icon: paths.chart, label: "Investment inquiry", query: "I am considering a property investment. Ask about my goals and explain only what current verified company information supports." },
            { icon: paths.calendar, label: "Payment plans", query: "Tell me about payment plans only when they are included in a verified available listing." },
          ].map((chip) => (
            <button
              key={chip.label}
              type="button"
              className="quick-chip-btn"
              onClick={() => void performAction(chip.query, chip.label)}
            >
              <span className="quick-chip-icon"><Icon>{chip.icon}</Icon></span>
              <span>{chip.label}</span>
            </button>
          ))}
        </div>

        {/* Command Input Bar */}
        <form
          className="orbit-input-box"
          onSubmit={(e) => {
            e.preventDefault();
            void send();
          }}
        >
          <input
            ref={textInputRef}
            type="text"
            className="orbit-cmd-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about budget, location, property, or booking…"
            aria-label="Type a message to the real estate assistant"
          />
          <button type="submit" className="orbit-cmd-submit" aria-label="Send Command">
            <Icon>{paths.send}</Icon>
          </button>
        </form>
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
              <button
                type="button"
                className="drawer-close-btn"
                onClick={() => setShowDrawer(false)}
                aria-label="Close conversation panel"
              >
                <Icon>{paths.close}</Icon>
              </button>
            </div>
          </div>

          <span className="drawer-copy-status" role="status" aria-live="polite">
            {conversationCopyStatus}
          </span>

          {(lastTiming || agentDecisionLatencyMs !== null || substantiveAnswerLatencyMs !== null) && (
            <details className="conversation-diagnostics">
              <summary>Voice timing details</summary>
              <dl>
                {lastTiming && (
                  <div>
                    <dt>{lastTiming.label}</dt>
                    <dd>{lastTiming.milliseconds.toLocaleString()} ms</dd>
                  </div>
                )}
                {agentDecisionLatencyMs !== null && (
                  <div>
                    <dt>Agent decision</dt>
                    <dd>{agentDecisionLatencyMs.toLocaleString()} ms</dd>
                  </div>
                )}
                {substantiveAnswerLatencyMs !== null && (
                  <div>
                    <dt>First answer audio</dt>
                    <dd>{substantiveAnswerLatencyMs.toLocaleString()} ms</dd>
                  </div>
                )}
              </dl>
              <p>Timings are local diagnostics; they do not measure human-perceived audio quality.</p>
            </details>
          )}

          <div className="drawer-scroll-body">
            {/* Messages */}
            <div className="drawer-messages-list" role="log" aria-label="Conversation messages" aria-live="polite" aria-relevant="additions">
              {messages.length === 0 ? (
                <div className="conversation-start-state" role="status">
                  <span className="conversation-start-eyebrow">LIVE CONVERSATION</span>
                  <p>No messages yet</p>
                  <small>Start a voice conversation or type a question. Replies will appear here after the live assistant responds.</small>
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

            {matches.length === 0 && (
              <div className="conversation-empty-state" role="status">
                {inventoryLoadState === "loading" ? (
                  <p>Loading the company’s current property inventory…</p>
                ) : inventoryLoadState === "error" ? (
                  <>
                    <p>Could not load live property inventory. Recommendations and visit requests are unavailable until it reconnects.</p>
                    <button type="button" onClick={() => {
                      setInventoryLoadState("loading");
                      setInventoryRefreshKey((current) => current + 1);
                    }}>Retry inventory</button>
                  </>
                ) : inventoryProperties.length === 0 ? (
                  <>
                    <p>No real company listings are loaded. The assistant will not invent properties; recommendations and visits need live inventory.</p>
                    <button type="button" onClick={() => setShowLocations(true)}>Check inventory</button>
                  </>
                ) : (
                  <p>No personalized recommendations yet. Ask the assistant to search the loaded listings.</p>
                )}
              </div>
            )}

            {/* Properties Cards Grid */}
            {matches.length > 0 && (
              <div className="drawer-properties-grid">
                {matches.map((id) => {
                  const prop = propertyDetails[id];
                  const detailsLoading = loadingPropertyIds.includes(id);
                  const isCompared = comparedPropertyIds.includes(id);
                  return (
                    <div key={id} className="drawer-property-item">
                      <div className="item-head">
                        <span className="prop-id">{id}</span>
                        <span className="prop-purpose">{prop?.purpose.toUpperCase() ?? (detailsLoading ? "LOADING" : "DETAILS UNAVAILABLE")}</span>
                      </div>
                      <h4 className="prop-title">{prop?.title ?? (detailsLoading ? "Loading inventory details…" : `Property ${id}`)}</h4>
                      <div className="prop-geo">{prop ? `${prop.area}, ${prop.city}` : "Inventory details unavailable"}</div>
                      <div className="prop-price">{prop ? formatPricePKR(prop.price_pkr) : "—"}</div>
                      {prop && (
                        <div className="prop-badges">
                          <span className="unit-badge">{getMarlaEquivalent(prop.size_sqft)}</span>
                          <span className={`availability-badge ${prop.available ? "available" : "unavailable"}`}>
                            {availabilityLabel(prop.available)}
                          </span>
                        </div>
                      )}
                      {prop && (
                        <div className="prop-source">
                          {inventorySourceLabel(prop.source, prop.source_version)}
                        </div>
                      )}
                      {prop && (
                        <div className="prop-specs">
                          <span>{prop.bedrooms > 0 ? `${prop.bedrooms} Bed` : "Commercial"}</span>
                          <span>•</span>
                          <span>{prop.size_sqft.toLocaleString()} sq ft</span>
                          <span>•</span>
                          <span>{prop.payment_plan}</span>
                        </div>
                      )}
                      <div className="prop-actions-row">
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
                          {canRequestVisit(prop) ? "Request a visit" : "Unavailable"}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
            <div ref={chatBottomRef} />
          </div>
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

      <AnalyticsPanel apiUrl={apiUrl} open={showAnalytics} onClose={() => setShowAnalytics(false)} />

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
          <p className="dialog-info">Submit a visit request for an available listing. Calendar confirmation is shown separately after the request is accepted.</p>
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
              <label>Requested visit time (Pakistan time)</label>
              <input
                aria-label="Requested visit date and time in Pakistan time"
                type="datetime-local"
                value={appointmentForm.starts_at}
                onChange={(e) => setAppointmentForm({ ...appointmentForm, starts_at: e.target.value })}
              />
              <span className="visit-slot-hint">Monday–Saturday, 10:00–17:30 PKT; start times are every 30 minutes.</span>
            </div>

            <div className="field-block">
              <label>Your Full Name</label>
              <input
                aria-label="Your name"
                placeholder="e.g. Haroon Shahid"
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
                onChange={(e) => setAppointmentForm({ ...appointmentForm, contact_email: e.target.value })}
              />
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
            disabled={!availableMatches.includes(selectedPropertyId) || !appointmentForm.client_name || !appointmentForm.contact_email || !appointmentForm.consent || Boolean(appointmentSlotError) || appointmentStatus === "Scheduling site visit…"}
          >
            Send visit request
          </button>
          {appointmentStatus && <p className={`appointment-note tone-${appointmentTone}`} role="status">{appointmentStatus}</p>}
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

      {/* Inventory locations dialog */}
      {showLocations && (
        <PropertyLocations
          properties={inventoryProperties}
          apiUrl={apiUrl}
          loadState={inventoryLoadState}
          onRetry={() => {
            setInventoryLoadState("loading");
            setInventoryRefreshKey((current) => current + 1);
          }}
          onImportComplete={() => {
            setInventoryLoadState("loading");
            setInventoryRefreshKey((current) => current + 1);
          }}
          onClose={() => setShowLocations(false)}
          onSelectProperty={(id) => {
            setSelectedPropertyId(id);
            const property = inventoryProperties.find((item) => item.id === id);
            if (property) setPropertyDetails((current) => ({ ...current, [id]: property }));
            setShowDrawer(true);
          }}
          onBook={(id) => {
            setShowLocations(false);
            openBookingFor(id);
          }}
        />
      )}

      {/* Mortgage & Financing Calculator Modal */}
      {showMortgageCalc && (
        <MortgageCalculatorModal
          property={propertyDetails[selectedPropertyId] || Object.values(propertyDetails)[0] || null}
          onClose={() => setShowMortgageCalc(false)}
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
