import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { NeuralOrb } from "./NeuralOrb";
import { OrbitalLaserBeams } from "./OrbitalLaserBeams";
import { WaveformVisualizer } from "./WaveformVisualizer";
import { BrowserAudioCapture, BrowserAudioPlayback } from "./voiceAudio";
import { parseServerEvent, shouldInterruptPlayback, audioUplinkState } from "./voiceProtocol";
import { closeVoiceSession, resolveLiveVoiceAction, VoiceInputGate, VoiceResponseTracker } from "./voiceConversation";
import { BoundedAudioReplay } from "./voiceReplay";
import { PropertyComparisonHUD } from "./PropertyComparisonHUD";
import { PropertyMapRadar } from "./PropertyMapRadar";
import { MortgageCalculatorModal } from "./MortgageCalculatorModal";
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
  assigned_employee: string;
  source?: string;
};

type Message = { role: "customer" | "agent"; text: string; time: string };
type RuntimeReadiness = { ready: boolean; mode: string; providers: Record<string, boolean> };
type VoicePhase = "checking" | "blocked" | "idle" | "connecting" | "authenticating" | "listening" | "thinking" | "speaking" | "error";
type FeedbackTone = "info" | "pending" | "success" | "error";
type VoiceMode = "standard" | "openai";

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
  close: "M18 6 6 18 M6 6l12 12",
  building: "M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z M6 12h12 M6 7h12 M6 17h12",
  settings: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z",
};

const voicePhaseLabels: Record<VoicePhase, string> = {
  checking: "Establishing orbital connection…",
  blocked: "Live voice is unavailable. Check provider readiness before starting a call.",
  idle: "Awaaz Neural Orbit Ready — Click Orb to speak",
  connecting: "Connecting voice session…",
  authenticating: "Authenticating security token…",
  listening: "Listening… Speak your requirement",
  thinking: "Finding verified matching properties…",
  speaking: "Awaaz Estate is responding…",
  error: "Voice connection error — Click Orb to retry",
};

function App() {
  const [activeActionLabel, setActiveActionLabel] = useState<string>("SYSTEM STANDBY — ORBIT READY");
  const [subtitles, setSubtitles] = useState("");
  const [voicePhase, setVoicePhase] = useState<VoicePhase>("checking");
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "agent",
      text: "Assalam-o-Alaikum! Welcome to Awaaz Estate. Speak directly or click any action node around the orbit to begin.",
      time: stamp(),
    },
  ]);
  const [matches, setMatches] = useState<string[]>([]);
  const [propertyDetails, setPropertyDetails] = useState<Record<string, Property>>({});
  const [socket, setSocket] = useState<WebSocket | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [voiceMode] = useState<VoiceMode>("openai");
  const [language, setLanguage] = useState<"ur-Latn" | "ur-Arab" | "en" | "hi" | "ar" | "pa" | "bn">("ur-Latn");
  const [audioAvailable, setAudioAvailable] = useState(false);
  const [audioInputs, setAudioInputs] = useState<MediaDeviceInfo[]>([]);
  const [selectedInputId, setSelectedInputId] = useState("");
  const [audioOutputUnavailable, setAudioOutputUnavailable] = useState(false);
  const [appointmentStatus, setAppointmentStatus] = useState("");
  const [appointmentTone, setAppointmentTone] = useState<FeedbackTone>("info");
  const [runtimeReadiness, setRuntimeReadiness] = useState<RuntimeReadiness | null>(null);
  const [selectedPropertyId, setSelectedPropertyId] = useState<string>("");
  const [showDrawer, setShowDrawer] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [comparedPropertyIds, setComparedPropertyIds] = useState<string[]>([]);
  const [showCompareHUD, setShowCompareHUD] = useState(false);
  const [showMapRadar, setShowMapRadar] = useState(false);
  const [showMortgageCalc, setShowMortgageCalc] = useState(false);
  const [lastLatencyMs, setLastLatencyMs] = useState<number | null>(null);
  const [activeNodeId, setActiveNodeId] = useState<string | null>(null);
  const [audioAnalyser, setAudioAnalyser] = useState<AnalyserNode | null>(null);
  const stageRef = useRef<HTMLDivElement | null>(null);
  const httpTurnAbort = useRef<AbortController | null>(null);

  const getTomorrowDefaultIso = () => {
    const d = new Date();
    d.setDate(d.getDate() + 1);
    d.setHours(11, 0, 0, 0);
    return d.toISOString().slice(0, 16);
  };

  const [appointmentForm, setAppointmentForm] = useState({
    client_name: "",
    contact_email: "",
    contact_phone: "",
    starts_at: getTomorrowDefaultIso(),
    consent: true,
  });

  const conversationId = useRef(
    typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `conv-${Date.now()}`
  );
  const bookingDialog = useRef<HTMLDialogElement | null>(null);
  const replayAudio = useRef(new BoundedAudioReplay());
  const capture = useRef<BrowserAudioCapture | null>(null);
  const finishSpeech = useRef<(() => void) | null>(null);
  const selectedInputRef = useRef("");
  const playback = useRef(new BrowserAudioPlayback());
  const responses = useRef(new VoiceResponseTracker());
  const serverPhase = useRef<VoicePhase>("idle");
  const sttRestarts = useRef(0);
  const languageRef = useRef(language);
  const voiceModeRef = useRef<VoiceMode>(voiceMode);
  const chatBottomRef = useRef<HTMLDivElement | null>(null);

  const connected = socket?.readyState === WebSocket.OPEN;
  const readinessKey = voiceMode === "openai" ? "openai_voice_ready" : "standard_voice_ready";
  const voiceReady = runtimeReadiness?.providers[readinessKey] === true;
  const displayVoicePhase: VoicePhase = audioOutputUnavailable ? "error" : voicePhase;

  useEffect(() => {
    voiceModeRef.current = voiceMode;
  }, [voiceMode]);

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, matches, showDrawer]);

  // Load properties preview
  useEffect(() => {
    void fetch(`${apiUrl}/v1/properties`)
      .then((res) => (res.ok ? res.json() : []))
      .then((data: Property[]) => {
        if (Array.isArray(data) && data.length > 0) {
          const map: Record<string, Property> = {};
          const ids: string[] = [];
          for (const item of data.slice(0, 4)) {
            map[item.id] = item;
            ids.push(item.id);
          }
          setPropertyDetails(map);
          setMatches(ids);
          setSelectedPropertyId(ids[0] ?? "");
        } else {
          setPropertyDetails({});
          setMatches([]);
          setSelectedPropertyId("");
        }
      })
      .catch(() => undefined);
  }, []);

  // Check server readiness
  useEffect(() => {
    let active = true;
    const refreshReadiness = async () => {
      try {
        const response = await fetch(`${apiUrl}/readyz`);
        if (!response.ok) throw new Error("Readiness check failed");
        const value = await response.json();
        const rawProviders = value.providers || {};
        const providers = Object.fromEntries(
          Object.entries(rawProviders).filter((entry): entry is [string, boolean] => typeof entry[1] === "boolean")
        );
        if (!active) return;
        const configured = providers[readinessKey] === true;
        setRuntimeReadiness({
          ready: value.status === "ready",
          mode: value.mode || "unknown",
          providers,
        });
        setVoicePhase((current) =>
          ["connecting", "authenticating", "listening", "thinking", "speaking", "error"].includes(current)
            ? current
            : configured ? "idle" : "blocked"
        );
      } catch {
        if (active) {
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
  }, [readinessKey]);

  function changeLanguage(next: "ur-Latn" | "ur-Arab" | "en" | "hi" | "ar" | "pa" | "bn") {
    setLanguage(next);
    languageRef.current = next;
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: "set_language", language: next }));
    }
  }

  async function startCapture(ws: WebSocket, mode: VoiceMode) {
    const nextCapture = new BrowserAudioCapture();
    capture.current = nextCapture;
    const inputGate = new VoiceInputGate();
    let audioSessionStarted = false;
    let stoppedForBackpressure = false;
    let manuallyCommitted = false;
    let silentInputMs = 0;
    let inputSignalSeen = false;
    finishSpeech.current = () => {
      if (capture.current !== nextCapture || ws.readyState !== WebSocket.OPEN) return;
      manuallyCommitted = true;
      inputGate.end();
      ws.send(JSON.stringify({ type: "audio_turn_end" }));
      setActiveActionLabel("LIVE ACTION: PROCESSING YOUR SPEECH");
    };
    try {
      await nextCapture.start(
        (chunk) => {
          if (stoppedForBackpressure || capture.current !== nextCapture) return;
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
            setActiveActionLabel("VOICE PAUSED — CONNECTION SLOW");
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
            setActiveActionLabel("MICROPHONE STREAM PAUSED");
          }
        },
        () => {
          if (ws.readyState !== WebSocket.OPEN) return;
          ws.send(JSON.stringify({ type: "set_language", language: languageRef.current }));
          ws.send(JSON.stringify({ type: "audio_start", sample_rate: 16_000, encoding: "linear16" }));
          audioSessionStarted = true;
        },
        mode === "openai"
          ? {
              onSpeechStart: () => {
                manuallyCommitted = false;
                responses.current.interrupt();
                playback.current.stop();
                setVoicePhase("listening");
                setActiveActionLabel("LIVE ACTION: USER SPEAKING INTO ORBIT");
                if (ws.readyState === WebSocket.OPEN) {
                  ws.send(JSON.stringify({ type: "audio_turn_start" }));
                  for (const frame of inputGate.start()) ws.send(frame);
                }
              },
              onSpeechEnd: () => {
                inputGate.end();
                if (manuallyCommitted) {
                  manuallyCommitted = false;
                  return;
                }
                setActiveActionLabel("LIVE ACTION: PROCESSING NEURAL TURN");
                if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "audio_turn_end" }));
              },
              onLevel: (rms, frameMs) => {
                if (inputSignalSeen) return;
                if (rms >= 0.0001) {
                  inputSignalSeen = true;
                } else {
                  silentInputMs += frameMs;
                  if (silentInputMs >= 4_000 && silentInputMs - frameMs < 4_000) {
                    setActiveActionLabel("NO MIC SOUND DETECTED — SPEAK OR SELECT MICROPHONE");
                  }
                }
              },
              onCaptureStalled: () => {
                if (capture.current !== nextCapture) return;
                capture.current = null;
                finishSpeech.current = null;
                setAudioAvailable(false);
                setAudioAnalyser(null);
                setActiveActionLabel("MICROPHONE STREAM STOPPED — RESTART VOICE CHAT");
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
      setAudioAvailable(true);
      setAudioAnalyser(nextCapture.getAnalyser());
      setActiveActionLabel("LIVE ORBITAL LINK ACTIVE — SPEAK FREELY");
      void navigator.mediaDevices.enumerateDevices()
        .then((devices) => setAudioInputs(devices.filter((device) => device.kind === "audioinput")))
        .catch(() => undefined);
    } catch {
      nextCapture.stop();
      if (capture.current === nextCapture) capture.current = null;
      finishSpeech.current = null;
      if (audioSessionStarted && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "audio_end" }));
      }
      setAudioAvailable(false);
      setAudioAnalyser(null);
      setActiveActionLabel("MICROPHONE UNAVAILABLE — TYPE IN COMMAND DOCK");
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

  async function connect() {
    if (connecting || connected) return;
    setConnecting(true);
    setVoicePhase("connecting");
    setActiveActionLabel("ACTION: INITIALIZING ORBITAL VOICE SESSION…");
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
      const ws = new WebSocket(wsUrl);
      ws.binaryType = "arraybuffer";
      ws.onopen = () => {
        setConnecting(false);
        setVoicePhase("authenticating");
        setActiveActionLabel("ACTION: AUTHENTICATING ORBITAL LINK…");
        ws.send(JSON.stringify({ type: "authenticate", ticket: session.ticket }));
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
        setActiveActionLabel("ORBITAL LINK ESTABLISHED — READY");
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
        if (event.code === 1013) {
          setVoicePhase("error");
          setActiveActionLabel(event.reason || "VOICE SERVICE BUSY — RETRY SHORTLY");
        } else if (event.code === 1008) {
          setVoicePhase("error");
          setActiveActionLabel(event.reason ? `REJECTED: ${event.reason}` : "AUTHENTICATION FAILED");
        } else if (event.code !== 1000) {
          setVoicePhase("error");
          setActiveActionLabel(event.reason ? `DISCONNECTED (${event.code}): ${event.reason}` : `VOICE CONNECTION LOST (${event.code}) — CHECK API AND NETWORK`);
        } else {
          setVoicePhase("idle");
          setActiveActionLabel("ORBITAL SESSION CLOSED — READY");
        }
      };
      ws.onerror = () => {
        setConnecting(false);
        setVoicePhase("error");
        setActiveActionLabel(`CONNECTION ERROR: COULD NOT REACH ${wsUrl}`);
      };
      ws.onmessage = (messageEvent) => {
        const raw: unknown = messageEvent.data;
        if (typeof raw !== "string") return;
        const event = parseServerEvent(raw);
        if (!event || !responses.current.accept(event)) return;
        if (shouldInterruptPlayback(event)) playback.current.stop();
        if (event.type === "state" && event.state) {
          const nextPhase = (event.state === "processing" ? "thinking" : event.state) as VoicePhase;
          serverPhase.current = nextPhase;
          setVoicePhase(nextPhase);
          if (nextPhase === "listening") setActiveActionLabel("LIVE ACTION: ORBIT LISTENING TO SPEECH");
          if (typeof event.audio_input_available === "boolean") {
            if (event.audio_input_available && !capture.current) void startCapture(ws, voiceModeRef.current);
          }
        }
        if (event.type === "transcript" && !event.is_final && event.text) {
          setActiveActionLabel(`HEARING: ${event.text.slice(-120)}`);
        }
        if (event.type === "transcript" && event.is_final && event.speech_final && event.text) {
          sttRestarts.current = 0;
          setVoicePhase("thinking");
          setActiveActionLabel(`USER SAID: "${event.text}"`);
          setMessages((current) => [...current, { role: "customer", text: event.text ?? "", time: stamp() }]);
        }
        if (event.type === "agent_response" && event.decision) {
          setVoicePhase("thinking");
          playback.current.stop();
          const text = event.decision.spoken_text;
          setSubtitles(text);
          replayAudio.current.reset();
          setAudioOutputUnavailable(false);
          setMessages((current) => [...current, { role: "agent", text, time: stamp() }]);
          if (typeof event.latency_ms === "number") setLastLatencyMs(Math.round(event.latency_ms));
          const ids = event.decision.property_ids ?? [];
          if (ids.length > 0) {
            setActiveActionLabel(`ACTION: FOUND ${ids.length} VERIFIED PROPERTIES`);
            setMatches(ids);
            if (!selectedPropertyId) setSelectedPropertyId(ids[0]);
            void Promise.all(
              ids.map(async (id) => {
                const response = await fetch(`${apiUrl}/v1/properties/${encodeURIComponent(id)}`);
                if (!response.ok) return null;
                return (await response.json()) as Property;
              })
            ).then((items) =>
              setPropertyDetails((current) => ({
                ...current,
                ...Object.fromEntries(
                  items.filter((item): item is Property => item !== null).map((item) => [item.id, item])
                ),
              }))
            );
          } else {
            setActiveActionLabel("PREPARING SPOKEN REPLY…");
          }
        }
        if (event.type === "agent_unavailable") {
          setVoicePhase("error");
          setActiveActionLabel("AGENT COULD NOT FINISH — PLEASE REPEAT THAT");
        }
        if (event.type === "stt_unavailable") {
          if (event.restart_required && event.recoverable && sttRestarts.current < 2 && capture.current) {
            sttRestarts.current += 1;
            setActiveActionLabel("RECONNECTING SPEECH RECOGNITION — PLEASE REPEAT");
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
            setVoicePhase("error");
            setActiveActionLabel("SPEECH RECOGNITION UNAVAILABLE — RESTART VOICE OR TYPE");
          }
        }
        if (event.type === "audio_unavailable") {
          setAudioOutputUnavailable(true);
          setActiveActionLabel("REPLY TEXT IS READY — SPOKEN AUDIO IS UNAVAILABLE");
        }
        if (event.type === "appointment_result") {
          setAppointmentTone("pending");
          const actionLabel = event.action === "cancellation" ? "CANCELLATION REQUESTED"
            : event.action === "reschedule" ? "RESCHEDULE REQUESTED" : "VISIT REQUESTED";
          const msg = `${actionLabel}: REF ${event.reference ?? ""} — CALENDAR/EMAIL PENDING`;
          setAppointmentStatus(msg);
          setActiveActionLabel(`ACTION: ${msg}`);
        }
        if (event.type === "audio_chunk") {
          setVoicePhase("speaking");
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
        }
      };
      setSocket(ws);
    } catch (err: unknown) {
      setConnecting(false);
      setVoicePhase("error");
      const msg = err instanceof Error ? err.message : "Failed to connect";
      setActiveActionLabel(`ERROR: ${msg}`);
    }
  }

  function playFuturisticTone(type: "listening" | "action" | "speaking") {
    if (typeof window === "undefined") return;
    try {
      const AudioCtx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      const now = ctx.currentTime;
      if (type === "listening") {
        osc.type = "sine";
        osc.frequency.setValueAtTime(440, now);
        osc.frequency.exponentialRampToValueAtTime(880, now + 0.12);
        gain.gain.setValueAtTime(0.08, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.25);
        osc.start(now);
        osc.stop(now + 0.25);
      } else if (type === "action") {
        osc.type = "triangle";
        osc.frequency.setValueAtTime(587.33, now);
        osc.frequency.setValueAtTime(880, now + 0.08);
        osc.frequency.setValueAtTime(1174.66, now + 0.16);
        gain.gain.setValueAtTime(0.06, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.3);
        osc.start(now);
        osc.stop(now + 0.3);
      } else if (type === "speaking") {
        osc.type = "sine";
        osc.frequency.setValueAtTime(659.25, now);
        gain.gain.setValueAtTime(0.05, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.2);
        osc.start(now);
        osc.stop(now + 0.2);
      }
    } catch {
      // AudioContext may require gesture
    }
  }

  function detectAndHighlightAction(text: string) {
    const t = text.toLowerCase();
    if (t.includes("karachi") || t.includes("clifton") || t.includes("2-bed") || t.includes("flat") || t.includes("sea view")) {
      setActiveNodeId("karachi-trends");
      setActiveActionLabel("ORBIT PERFORMING: KARACHI TRENDS QUERY");
    } else if (t.includes("lahore") || t.includes("gulberg") || t.includes("villa") || t.includes("house")) {
      setActiveNodeId("lahore-hotspots");
      setActiveActionLabel("ORBIT PERFORMING: LAHORE HOTSPOTS QUERY");
    } else if (t.includes("islamabad") || t.includes("blue area") || t.includes("commercial") || t.includes("office") || t.includes("shop")) {
      setActiveNodeId("islamabad-prime");
      setActiveActionLabel("ORBIT PERFORMING: ISLAMABAD COMMERCIAL QUERY");
    } else if (t.includes("installment") || t.includes("payment") || t.includes("plan") || t.includes("qist") || t.includes("aqsaat")) {
      setActiveNodeId("installment-plans");
      setActiveActionLabel("ORBIT PERFORMING: PAYMENT PLANS QUERY");
    } else if (t.includes("yield") || t.includes("roi") || t.includes("rental") || t.includes("kiraya") || t.includes("invest")) {
      setActiveNodeId("rental-yield");
      setActiveActionLabel("ORBIT PERFORMING: RENTAL YIELD CALCULATION");
    } else if (t.includes("briefing") || t.includes("market") || t.includes("overview") || t.includes("update") || t.includes("aaj")) {
      setActiveNodeId("daily-briefing");
      setActiveActionLabel("ORBIT PERFORMING: DAILY MARKET BRIEFING");
    } else if (t.includes("visit") || t.includes("schedule") || t.includes("book") || t.includes("dekhna") || t.includes("tour")) {
      setActiveNodeId("schedule-visit");
      setActiveActionLabel("ORBIT PERFORMING: SITE VISIT BOOKING");
    }
  }

  function unlockAudio() {
    void playback.current.activate().catch(() => undefined);
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
    } else if (resolveLiveVoiceAction(voiceReady) === "connect") {
      void connect();
    } else {
      setVoicePhase("blocked");
      setActiveActionLabel("LIVE VOICE IS NOT READY — CHECK PROVIDER READINESS");
    }
  }

  function disconnect() {
    finishSpeech.current = null;
    capture.current?.stop();
    capture.current = null;
    playback.current.stop();
    httpTurnAbort.current?.abort();
    httpTurnAbort.current = null;
    setAudioAnalyser(null);
    closeVoiceSession(socket);
    setSocket(null);
    setAudioAvailable(false);
    setVoicePhase("idle");
    setActiveActionLabel("VOICE CALL DISCONNECTED — READY");
  }

  async function performAction(queryText: string, actionLabel: string, nodeId?: string) {
    unlockAudio();
    if (nodeId) setActiveNodeId(nodeId);
    else detectAndHighlightAction(queryText);
    setActiveActionLabel(`ACTION: ${actionLabel.toUpperCase()}`);
    setShowDrawer(true);
    playFuturisticTone("action");
    await send(queryText);
  }

  async function send(overrideText?: string) {
    const text = (overrideText ?? input).trim();
    if (!text) return;
    setInput("");
    responses.current.interrupt();
    playback.current.stop();
    unlockAudio();
    setMessages((current) => [...current, { role: "customer", text, time: stamp() }]);
    setVoicePhase("thinking");
    detectAndHighlightAction(text);
    setActiveActionLabel(`PROCESSING: "${text.slice(0, 32)}…"`);

    // If WebSocket is active, send via real-time socket
    if (socket && socket.readyState === WebSocket.OPEN) {
      httpTurnAbort.current?.abort();
      httpTurnAbort.current = null;
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
      setLastLatencyMs(Math.round(performance.now() - start));
      const decision = data.decision || data;
      const reply =
        decision.spoken_text ||
        decision.text ||
        data.spoken_text ||
        data.text ||
        "Main aapki madad kar sakta hoon.";
      setSubtitles(reply);
      setMessages((current) => [...current, { role: "agent", text: reply, time: stamp() }]);
      setActiveActionLabel("ACTION: RESPONSE DELIVERED");
      setVoicePhase("idle");

      const ids: string[] = decision.property_ids || data.property_ids || [];
      if (ids.length > 0) {
        setMatches(ids);
        if (!selectedPropertyId) setSelectedPropertyId(ids[0]);
        setShowDrawer(true);
        void Promise.all(
          ids.map(async (id) => {
            const r = await fetch(`${apiUrl}/v1/properties/${encodeURIComponent(id)}`);
            if (!r.ok) return null;
            return (await r.json()) as Property;
          })
        ).then((items) =>
          setPropertyDetails((current) => ({
            ...current,
            ...Object.fromEntries(
              items.filter((item): item is Property => item !== null).map((item) => [item.id, item])
            ),
          }))
        );
      }
      playFuturisticTone("speaking");
    } catch (error: unknown) {
      if (error instanceof Error && error.name === "AbortError") return;
      if (httpTurnAbort.current !== controller) return;
      setVoicePhase("error");
      setActiveActionLabel("LIVE AI TURN FAILED — CHECK BACKEND AND PROVIDER STATUS");
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
    if (!selectedPropertyId || !propertyDetails[selectedPropertyId]) {
      setAppointmentTone("error");
      setAppointmentStatus("Import a real available property before requesting a visit.");
      setActiveActionLabel("BOOKING BLOCKED — NO VERIFIED PROPERTY SELECTED");
      return;
    }
    setActiveActionLabel("ACTION: BOOKING SITE VISIT…");
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
          starts_at: appointmentForm.starts_at ? new Date(appointmentForm.starts_at).toISOString() : new Date(Date.now() + 86400000).toISOString(),
          consent: true,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Booking failed");
      setAppointmentTone("pending");
      setAppointmentStatus(`Visit request recorded. Calendar confirmation pending — reference ${data.reference}.`);
      setActiveActionLabel(`ACTION: VISIT REQUEST RECORDED (${data.reference})`);
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
      setActiveActionLabel("ACTION FAILED: COULD NOT BOOK VISIT");
    }
  }

  function openBookingFor(propertyId: string) {
    setSelectedPropertyId(propertyId);
    bookingDialog.current?.showModal();
  }

  return (
    <main className="orbit-platform" aria-label="Awaaz Estate Neural Orbit Platform">
      {/* Top HUD Bar */}
      <header className="orbit-header">
        <div className="orbit-brand">
          <div className="orbit-logo-crest">
            <Icon>{paths.spark}</Icon>
          </div>
          <div className="orbit-title-group">
            <span className="orbit-brand-title">Awaaz Estate</span>
            <span className="orbit-version-badge">NEURAL ORBIT v1.0</span>
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
          >
            <Icon>{paths.settings}</Icon>
          </button>

          <div className={`orbit-status-chip ${connected ? "live" : voiceReady ? "ready" : "offline"}`}>
            <span className="status-dot" />
            <span>{connected ? "LIVE OPENAI VOICE" : voiceReady ? "LIVE READY" : "VOICE OFFLINE"}</span>
          </div>
        </div>
      </header>

      {/* Main Orbit Stage — Centered & Immersive */}
      <div className="orbit-center-stage" ref={stageRef}>
        <OrbitalLaserBeams activeNodeId={activeNodeId} stageRef={stageRef} />

        {/* Left Orbital Action Nodes (Surrounding the Orbit) */}
        <div className="orbital-nodes-col left-nodes" aria-label="Left Orbital Command Nodes">
          <div
            data-node-id="daily-briefing"
            className={`orbital-node-card ${activeNodeId === "daily-briefing" ? "active-performing" : ""}`}
            onClick={() => void performAction("Give me today's real estate market briefing", "Daily Briefing", "daily-briefing")}
          >
            <div className={`node-dot-pin ${activeNodeId === "daily-briefing" ? "pulsing" : ""}`} />
            <div className="node-content">
              <span className="node-title">Daily Briefing</span>
              <span className="node-sub">Market Overview</span>
            </div>
            <span className={`node-tag ${activeNodeId === "daily-briefing" ? "green" : ""}`}>
              {activeNodeId === "daily-briefing" ? "ACTIVE" : "BRIEF"}
            </span>
          </div>

          <div
            data-node-id="karachi-trends"
            className={`orbital-node-card ${activeNodeId === "karachi-trends" ? "active-performing" : ""}`}
            onClick={() => void performAction("Show me 2-bedroom flats in Karachi Clifton and DHA", "Karachi Trends", "karachi-trends")}
          >
            <div className={`node-dot-pin ${activeNodeId === "karachi-trends" ? "pulsing" : ""}`} />
            <div className="node-content">
              <span className="node-title">Karachi Trends</span>
              <span className="node-sub">Clifton & DHA</span>
            </div>
            <span className={`node-tag ${activeNodeId === "karachi-trends" ? "cyan" : ""}`}>
              {activeNodeId === "karachi-trends" ? "ACTIVE" : "2-BED"}
            </span>
          </div>

          <div
            data-node-id="lahore-hotspots"
            className={`orbital-node-card ${activeNodeId === "lahore-hotspots" ? "active-performing" : ""}`}
            onClick={() => void performAction("Show me luxury villas in DHA Lahore", "Lahore Hotspots", "lahore-hotspots")}
          >
            <div className={`node-dot-pin ${activeNodeId === "lahore-hotspots" ? "pulsing" : ""}`} />
            <div className="node-content">
              <span className="node-title">Lahore Hotspots</span>
              <span className="node-sub">DHA Villas</span>
            </div>
            <span className={`node-tag ${activeNodeId === "lahore-hotspots" ? "purple" : ""}`}>
              {activeNodeId === "lahore-hotspots" ? "ACTIVE" : "PRIME"}
            </span>
          </div>

          <div
            data-node-id="islamabad-prime"
            className={`orbital-node-card ${activeNodeId === "islamabad-prime" ? "active-performing" : ""}`}
            onClick={() => void performAction("Show me commercial offices in Islamabad Blue Area", "Islamabad Commercial", "islamabad-prime")}
          >
            <div className={`node-dot-pin ${activeNodeId === "islamabad-prime" ? "pulsing" : ""}`} />
            <div className="node-content">
              <span className="node-title">Islamabad Prime</span>
              <span className="node-sub">Blue Area</span>
            </div>
            <span className={`node-tag ${activeNodeId === "islamabad-prime" ? "cyan" : ""}`}>
              {activeNodeId === "islamabad-prime" ? "ACTIVE" : "COMM"}
            </span>
          </div>
        </div>

        {/* Center: The Core 3D Holographic Orbit */}
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
            <div className={`orbit-state-pill phase-${displayVoicePhase}`}>
              {displayVoicePhase === "error" ? activeActionLabel : voicePhaseLabels[displayVoicePhase]}
            </div>
            {subtitles && <p className="orbit-subtitles-stream">"{subtitles}"</p>}
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
                    setActiveActionLabel("SPEECH STOPPED");
                  }
                  if (socket?.readyState === WebSocket.OPEN) {
                    setVoicePhase("listening");
                    setActiveActionLabel("BARGE-IN TRIGGERED — LISTENING");
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
            isActive={connected && (displayVoicePhase === "speaking" || displayVoicePhase === "listening")}
          />
        </div>

        {/* Right Orbital Action Nodes (Surrounding the Orbit) */}
        <div className="orbital-nodes-col right-nodes" aria-label="Right Orbital Telemetry Nodes">
          <div
            data-node-id="installment-plans"
            className={`orbital-node-card ${activeNodeId === "installment-plans" ? "active-performing" : ""}`}
            onClick={() => void performAction("Explain installment and payment plans for Clifton apartments", "Payment Plans", "installment-plans")}
          >
            <span className={`node-tag ${activeNodeId === "installment-plans" ? "green" : "purple"}`}>
              {activeNodeId === "installment-plans" ? "ACTIVE" : "PLAN"}
            </span>
            <div className="node-content text-right">
              <span className="node-title">Installment Plans</span>
              <span className="node-sub">Flexible Payment</span>
            </div>
            <div className={`node-dot-pin ${activeNodeId === "installment-plans" ? "pulsing" : ""}`} />
          </div>

          <div
            data-node-id="rental-yield"
            className={`orbital-node-card ${activeNodeId === "rental-yield" ? "active-performing" : ""}`}
            onClick={() => void performAction("Compare rental yields between Karachi and Lahore DHA", "Rental Yield", "rental-yield")}
          >
            <span className={`node-tag ${activeNodeId === "rental-yield" ? "cyan" : "green"}`}>
              {activeNodeId === "rental-yield" ? "ACTIVE" : "ROI"}
            </span>
            <div className="node-content text-right">
              <span className="node-title">Rental Yield</span>
              <span className="node-sub">ROI Analyzer</span>
            </div>
            <div className={`node-dot-pin ${activeNodeId === "rental-yield" ? "pulsing" : ""}`} />
          </div>

          <div
            data-node-id="schedule-visit"
            className={`orbital-node-card ${activeNodeId === "schedule-visit" ? "active-performing" : ""}`}
            onClick={() => {
              setActiveNodeId("schedule-visit");
              playFuturisticTone("action");
              bookingDialog.current?.showModal();
            }}
          >
            <span className={`node-tag ${activeNodeId === "schedule-visit" ? "purple" : "cyan"}`}>
              {activeNodeId === "schedule-visit" ? "OPEN" : "BOOK"}
            </span>
            <div className="node-content text-right">
              <span className="node-title">Schedule Visit</span>
              <span className="node-sub">Site Tour</span>
            </div>
            <div className={`node-dot-pin ${activeNodeId === "schedule-visit" ? "pulsing" : ""}`} />
          </div>

          <div
            data-node-id="live-telemetry"
            className={`orbital-node-card telemetry-node ${activeNodeId === "live-telemetry" ? "active-performing" : ""}`}
            onClick={() => {
              setActiveNodeId("live-telemetry");
              playFuturisticTone("action");
              setShowMapRadar(true);
            }}
          >
            <span className="node-tag">{lastLatencyMs === null ? "—" : `${lastLatencyMs}ms`}</span>
            <div className="node-content text-right">
              <span className="node-title">Geospatial Radar</span>
              <span className="node-sub">Interactive Map HUD</span>
            </div>
            <div className="node-dot-pin green-pin" />
          </div>
        </div>
      </div>

      {/* Floating Bottom Dock (Directly beneath the Orbit) */}
      <div className="orbit-bottom-dock">
        <div className="orbit-dock-pill-bar">
          <button
            type="button"
            className={`dock-action-pill ${showDrawer ? "active" : ""}`}
            onClick={() => setShowDrawer(!showDrawer)}
            aria-label="Toggle Dialogue & Property Results"
          >
            <Icon>{paths.transcript}</Icon>
            <span>{showDrawer ? "Hide Results" : "Show Results"}</span>
            {matches.length > 0 && <span className="dock-count-badge">{matches.length}</span>}
          </button>

          <button
            type="button"
            className={`dock-action-pill ${showCompareHUD ? "active" : ""}`}
            onClick={() => {
              if (comparedPropertyIds.length === 0 && matches.length >= 2) {
                setComparedPropertyIds(matches.slice(0, 3));
              }
              setShowCompareHUD(true);
            }}
            aria-label="Side-by-side Property Comparison HUD"
          >
            <Icon>{paths.building}</Icon>
            <span>Compare</span>
            {comparedPropertyIds.length > 0 ? (
              <span className="dock-count-badge">{comparedPropertyIds.length}</span>
            ) : matches.length >= 2 ? (
              <span className="dock-count-badge">{Math.min(matches.length, 3)}</span>
            ) : null}
          </button>

          <button
            type="button"
            className={`dock-action-pill ${showMapRadar ? "active" : ""}`}
            onClick={() => setShowMapRadar(true)}
            aria-label="Open Geospatial Map Radar"
          >
            <Icon>{paths.home}</Icon>
            <span>Map Radar</span>
          </button>

          <button
            type="button"
            className={`dock-action-pill ${showMortgageCalc ? "active" : ""}`}
            onClick={() => setShowMortgageCalc(true)}
            aria-label="Open Mortgage and Installment Calculator"
          >
            <Icon>{paths.spark}</Icon>
            <span>Finance HUD</span>
          </button>

          <div className={`dock-asr-pill ${connected ? "live" : ""}`}>
            <span className="asr-led" />
            <span>ASR {connected ? (voiceMode === "openai" ? "OPENAI LIVE" : "DEEPGRAM LIVE") : "STANDBY"}</span>
          </div>

          {connected && audioAvailable && displayVoicePhase === "listening" && (
            <button type="button" className="dock-action-pill" onClick={() => finishSpeech.current?.()} aria-label="Finish speaking and get reply">
              <Icon>{paths.send}</Icon>
              <span>Reply now</span>
            </button>
          )}

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
        </div>

        {/* Quick Voice Query Chips */}
        <div className="orbit-quick-chips-row">
          {[
            { icon: "✨", label: "Clifton 2-Bed Luxury", query: "Show me 2-bedroom luxury apartments in Clifton Karachi", nodeId: "karachi-trends" },
            { icon: "🏡", label: "5 Marla DHA Lahore", query: "Show me 5 Marla and 10 Marla houses in DHA Lahore", nodeId: "lahore-hotspots" },
            { icon: "🏢", label: "Blue Area Islamabad", query: "Show me commercial offices in Blue Area Islamabad", nodeId: "islamabad-prime" },
            { icon: "📑", label: "FBR Tax Calculation", query: "Calculate FBR tax and transfer duty for 3 crore purchase", nodeId: "daily-briefing" },
            { icon: "💰", label: "Installment Plans", query: "Explain installment and payment plans for Clifton apartments", nodeId: "installment-plans" },
          ].map((chip) => (
            <button
              key={chip.label}
              type="button"
              className="quick-chip-btn"
              onClick={() => void performAction(chip.query, chip.label, chip.nodeId)}
            >
              <span className="quick-chip-icon">{chip.icon}</span>
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
            type="text"
            className="orbit-cmd-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type a command, or Start Talk..."
            aria-label="Command Input"
          />
          <button type="submit" className="orbit-cmd-submit" aria-label="Send Command">
            <Icon>{paths.send}</Icon>
          </button>
        </form>
      </div>

      {/* Expandable Results & Property Drawer */}
      {showDrawer && (
        <div className="orbit-floating-drawer" role="dialog" aria-label="Results and Property Cards">
          <div className="drawer-bar-top">
            <div className="drawer-title-wrap">
              <Icon>{paths.spark}</Icon>
              <span>Action Results & Verified Recommendations ({matches.length})</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
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
                  ⚖️ Compare ({comparedPropertyIds.length || Math.min(matches.length, 3)}) Side-by-Side
                </button>
              )}
              <button
                type="button"
                className="drawer-close-btn"
                onClick={() => setShowDrawer(false)}
                aria-label="Close Drawer"
              >
                <Icon>{paths.close}</Icon>
              </button>
            </div>
          </div>

          <div className="drawer-scroll-body">
            {/* Messages */}
            <div className="drawer-messages-list">
              {messages.map((m, idx) => (
                <div key={idx} className={`drawer-bubble role-${m.role}`}>
                  <span className="bubble-author">{m.role === "agent" ? "Awaaz Neural" : "You"}</span>
                  <div className="bubble-text">{m.text}</div>
                </div>
              ))}
            </div>

            {/* Properties Cards Grid */}
            {matches.length > 0 && (
              <div className="drawer-properties-grid">
                {matches.map((id) => {
                  const prop = propertyDetails[id];
                  const isCompared = comparedPropertyIds.includes(id);
                  return (
                    <div key={id} className="drawer-property-item">
                      <div className="item-head">
                        <span className="prop-id">{id}</span>
                        <span className="prop-purpose">{prop?.purpose ?? "VERIFIED"}</span>
                      </div>
                      <h4 className="prop-title">{prop?.title ?? `Verified Property ${id}`}</h4>
                      <div className="prop-geo">{prop ? `${prop.area}, ${prop.city}` : "Pakistan"}</div>
                      <div className="prop-price">{prop ? formatPricePKR(prop.price_pkr) : "Price on Inquiry"}</div>
                      {prop && (
                        <div className="prop-badges">
                          <span className="unit-badge">{getMarlaEquivalent(prop.size_sqft)}</span>
                          <span className="noc-badge">NOC VERIFIED</span>
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
                        >
                          Book Visit
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
            <div ref={chatBottomRef} />
          </div>
        </div>
      )}

      {/* Settings Modal Dialog */}
      {showSettingsModal && (
        <div className="orbit-modal-backdrop" onClick={() => setShowSettingsModal(false)}>
          <div className="orbit-modal-window" onClick={(e) => e.stopPropagation()}>
            <div className="modal-top">
              <h3>Neural Audio & Engine Settings</h3>
              <button type="button" className="modal-x-btn" onClick={() => setShowSettingsModal(false)}>✕</button>
            </div>
            <div className="modal-fields">
              <div className="form-row">
                <label>Voice Provider Engine</label>
                <div className="settings-value">OpenAI Realtime Voice Pipeline</div>
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
                <div className="settings-value">Generated by the configured OpenAI speech service</div>
              </div>
            </div>
            <div className="modal-foot">
              <button type="button" className="save-btn" onClick={() => setShowSettingsModal(false)}>Save & Close</button>
            </div>
          </div>
        </div>
      )}

      {/* Site Visit Booking Modal Dialog */}
      <dialog className="orbit-booking-dialog" ref={bookingDialog} aria-labelledby="booking-title">
        <div className="dialog-top-bar">
          <div className="dialog-title-wrap">
            <Icon>{paths.calendar}</Icon>
            <h2 id="booking-title">Schedule In-Person Site Visit</h2>
          </div>
          <button type="button" className="dialog-x" onClick={() => bookingDialog.current?.close()} aria-label="Close dialog">
            <Icon>{paths.close}</Icon>
          </button>
        </div>

        <section className="dialog-body">
          <p className="dialog-info">Confirm your details to book a site visit with our verified consultant.</p>
          <div className="dialog-grid">
            <div className="field-block">
              <label>Selected Property</label>
              <select
                aria-label="Select property"
                value={selectedPropertyId}
                onChange={(e) => setSelectedPropertyId(e.target.value)}
                className="dialog-select-input"
              >
                {matches.length > 0 ? (
                  matches.map((id) => (
                    <option key={id} value={id}>
                      {id} — {propertyDetails[id]?.title ?? "Property"} ({propertyDetails[id]?.city ?? "Pakistan"})
                    </option>
                  ))
                ) : (
                  <option value="" disabled>Import real property listings to schedule a visit</option>
                )}
              </select>
            </div>

            <div className="field-block">
              <label>Requested Visit Date & Time</label>
              <input
                aria-label="Requested visit date and time"
                type="datetime-local"
                value={appointmentForm.starts_at}
                onChange={(e) => setAppointmentForm({ ...appointmentForm, starts_at: e.target.value })}
              />
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
          </div>

          <button
            type="button"
            className="dialog-confirm-action"
            onClick={() => void bookVisit()}
            disabled={!appointmentForm.client_name || !appointmentForm.contact_email || appointmentStatus === "Scheduling site visit…"}
          >
            Confirm Site Visit Booking
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

      {/* Geospatial Property Map Radar Modal */}
      {showMapRadar && (
        <PropertyMapRadar
          properties={Object.values(propertyDetails)}
          onClose={() => setShowMapRadar(false)}
          onSelectProperty={(id) => {
            setSelectedPropertyId(id);
            setShowDrawer(true);
          }}
          onBook={(id) => {
            setShowMapRadar(false);
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
if (rootElement) {
  createRoot(rootElement).render(<App />);
}
