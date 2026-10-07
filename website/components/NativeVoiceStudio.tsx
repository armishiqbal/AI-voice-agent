"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import Link from "next/link";
import { ListingCard } from "@/components/ListingCard";
import { ActionCard, type ChatAction } from "@/components/ActionCard";
import { addToShortlist, removeFromShortlist } from "@/lib/favorites";
import type { Listing } from "@/lib/catalog";

type VoiceState = "idle" | "connecting" | "ready" | "listening" | "thinking" | "speaking" | "error";

interface ChatMessage {
  id: string;
  sender: "user" | "assistant";
  text: string;
  properties?: Listing[];
  actions?: ChatAction[];
  timestamp: string;
}

export function NativeVoiceStudio() {
  const [voiceState, setVoiceState] = useState<VoiceState>("idle");
  const [language, setLanguage] = useState<"ur-Latn" | "en">("ur-Latn");
  const [statusMessage, setStatusMessage] = useState("Tap the microphone or choose a question below to start.");
  const [liveTranscript, setLiveTranscript] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [textInput, setTextInput] = useState("");
  const [isMuted, setIsMuted] = useState(false);
  const [volumeLevel, setVolumeLevel] = useState(0.2);

  const socketRef = useRef<WebSocket | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const chatScrollRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll chat as conversation progresses
  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
    }
  }, [messages, liveTranscript]);

  // Clean up media streams and sockets on unmount
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, []);

  const disconnect = useCallback(() => {
    if (processorRef.current) {
      try { processorRef.current.disconnect(); } catch {}
      processorRef.current = null;
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }
    if (audioContextRef.current) {
      try { audioContextRef.current.close(); } catch {}
      audioContextRef.current = null;
    }
    if (socketRef.current) {
      try { socketRef.current.close(); } catch {}
      socketRef.current = null;
    }
    setVoiceState("idle");
    setStatusMessage("Voice session ended. Tap start to reconnect.");
    setLiveTranscript("");
  }, []);

  // Connect to the WebSocket voice pipeline
  const connectVoice = async () => {
    if (voiceState !== "idle" && voiceState !== "error") {
      disconnect();
      return;
    }

    setVoiceState("connecting");
    setStatusMessage("Requesting secure voice session ticket...");

    const backendUrl = (process.env.NEXT_PUBLIC_AWAAZ_API_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

    try {
      // 1. Obtain authenticated voice session ticket
      const sessionRes = await fetch(`${backendUrl}/v1/voice/session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: "hybrid" }),
      });

      if (!sessionRes.ok) {
        throw new Error("Could not acquire voice session ticket.");
      }

      const { ticket } = await sessionRes.json();
      const wsProtocol = backendUrl.startsWith("https") ? "wss:" : "ws:";
      const wsHost = backendUrl.replace(/^https?:\/\//, "");
      const wsUrl = `${wsProtocol}//${wsHost}/v1/voice?ticket=${encodeURIComponent(ticket)}`;

      setStatusMessage("Connecting to real-time speech pipeline...");
      const ws = new WebSocket(wsUrl);
      socketRef.current = ws;

      ws.onopen = async () => {
        setVoiceState("ready");
        setStatusMessage("Voice pipeline connected. Initializing microphone...");

        // Inform server of initial language selection
        ws.send(JSON.stringify({ type: "set_language", language }));

        // Start local audio capture
        try {
          await startMicrophoneCapture(ws);
          setVoiceState("listening");
          setStatusMessage("I am listening. Speak in Urdu or English...");
        } catch (micErr) {
          console.warn("Microphone not available, falling back to text voice session:", micErr);
          setVoiceState("ready");
          setStatusMessage("Voice pipeline ready for text and queries. Tap mic to retry audio.");
        }
      };

      ws.onmessage = async (event) => {
        if (typeof event.data === "string") {
          try {
            const data = JSON.parse(event.data);
            handleServerEvent(data);
          } catch (e) {
            console.error("Malformed voice packet:", e);
          }
        } else if (event.data instanceof Blob) {
          // Received synthesized speech audio from server
          playAudioBlob(event.data);
        }
      };

      ws.onerror = (err) => {
        console.error("Voice WebSocket error:", err);
        setVoiceState("error");
        setStatusMessage("Connection error with the voice server. Please retry.");
      };

      ws.onclose = () => {
        disconnect();
      };
    } catch (err) {
      console.error("Failed to start voice session:", err);
      setVoiceState("error");
      setStatusMessage("Unable to start voice session. Check server status or try again.");
    }
  };

  const executeClientAction = useCallback((action: ChatAction) => {
    if (!action || !action.kind) return;
    if (action.kind === "shortlist_property") {
      const propId = String(action.payload?.property_id || "");
      const actionType = String(action.payload?.action || "add");
      if (propId && propId !== "CURRENT_PROPERTY") {
        const slug = propId.toLowerCase();
        if (actionType === "add") {
          addToShortlist(slug);
        } else {
          removeFromShortlist(slug);
        }
      }
    }
  }, []);

  const handleServerEvent = (data: Record<string, unknown>) => {
    const type = data.type;

    if (type === "state") {
      const serverState = String(data.state || "");
      if (serverState === "listening") {
        setVoiceState("listening");
        setStatusMessage("Listening...");
      } else if (serverState === "thinking") {
        setVoiceState("thinking");
        setStatusMessage("Awaaz is thinking...");
      } else if (serverState === "speaking") {
        setVoiceState("speaking");
        setStatusMessage("Awaaz is speaking...");
      }
    } else if (type === "transcript") {
      const text = String(data.text || "");
      setLiveTranscript(text);
      if (data.is_final) {
        setMessages((prev) => [
          ...prev,
          {
            id: `user-${Date.now()}`,
            sender: "user",
            text,
            timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          },
        ]);
        setLiveTranscript("");
      }
    } else if (
      type === "agent_response" ||
      type === "assistant_text" ||
      type === "response"
    ) {
      const decision = (data.decision as Record<string, unknown>) || {};
      const text = String(data.text || data.spoken_text || decision.spoken_text || "");
      const incomingActions = (Array.isArray(data.actions)
        ? data.actions
        : Array.isArray(decision.actions)
        ? decision.actions
        : []) as ChatAction[];

      for (const act of incomingActions) {
        executeClientAction(act);
      }

      if (text || incomingActions.length > 0) {
        setMessages((prev) => [
          ...prev,
          {
            id: `assistant-${Date.now()}`,
            sender: "assistant",
            text: text || "Action executed successfully:",
            actions: incomingActions.length > 0 ? incomingActions : undefined,
            timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          },
        ]);
      }
    } else if (type === "action_executed") {
      const action = data.action as ChatAction;
      if (action) {
        executeClientAction(action);
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last && last.sender === "assistant") {
            const existingActions = last.actions || [];
            if (!existingActions.some((a) => a.id === action.id)) {
              return [
                ...prev.slice(0, -1),
                { ...last, actions: [...existingActions, action] },
              ];
            }
            return prev;
          }
          return [
            ...prev,
            {
              id: `action-${Date.now()}`,
              sender: "assistant",
              text: action.summary || "Action executed successfully:",
              actions: [action],
              timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
            },
          ];
        });
      }
    } else if (type === "property_matches" || type === "properties") {
      const listings = Array.isArray(data.properties) ? (data.properties as Listing[]) : [];
      if (listings.length > 0) {
        setMessages((prev) => [
          ...prev,
          {
            id: `props-${Date.now()}`,
            sender: "assistant",
            text: `I found ${listings.length} verified ${listings.length === 1 ? "property" : "properties"} matching your request:`,
            properties: listings,
            timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          },
        ]);
      }
    }
  };

  const startMicrophoneCapture = async (ws: WebSocket) => {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });
    mediaStreamRef.current = stream;

    const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    const audioCtx = new AudioContextClass({ sampleRate: 16000 });
    audioContextRef.current = audioCtx;

    const source = audioCtx.createMediaStreamSource(stream);
    const processor = audioCtx.createScriptProcessor(4096, 1, 1);
    processorRef.current = processor;

    ws.send(JSON.stringify({ type: "audio_start", sample_rate: 16000, encoding: "linear16" }));
    ws.send(JSON.stringify({ type: "audio_turn_start" }));

    processor.onaudioprocess = (e) => {
      if (ws.readyState !== WebSocket.OPEN) return;
      const inputData = e.inputBuffer.getChannelData(0);

      // Simple RMS calculation for volume visualizer
      let sum = 0;
      for (let i = 0; i < inputData.length; i++) {
        sum += inputData[i] * inputData[i];
      }
      const rms = Math.sqrt(sum / inputData.length);
      setVolumeLevel(Math.min(1, Math.max(0.1, rms * 5)));

      // Convert Float32 to 16-bit PCM (Linear16)
      const pcm16 = new Int16Array(inputData.length);
      for (let i = 0; i < inputData.length; i++) {
        const s = Math.max(-1, Math.min(1, inputData[i]));
        pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }
      ws.send(pcm16.buffer);
    };

    source.connect(processor);
    processor.connect(audioCtx.destination);
  };

  const playAudioBlob = (blob: Blob) => {
    try {
      const audioUrl = URL.createObjectURL(blob);
      const audio = new Audio(audioUrl);
      setVoiceState("speaking");
      audio.onended = () => {
        setVoiceState("listening");
        URL.revokeObjectURL(audioUrl);
      };
      audio.play().catch((err) => console.warn("Audio autoplay blocked by browser:", err));
    } catch (err) {
      console.error("Failed to play synthesized audio:", err);
    }
  };

  const handleSendText = (textToSend?: string) => {
    const text = (textToSend || textInput).trim();
    if (!text) return;

    // Add user message to UI immediately
    setMessages((prev) => [
      ...prev,
      {
        id: `user-${Date.now()}`,
        sender: "user",
        text,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      },
    ]);
    setTextInput("");

    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      setVoiceState("thinking");
      setStatusMessage("Awaaz is thinking...");
      socketRef.current.send(
        JSON.stringify({
          type: "text_turn",
          text,
          language,
        })
      );
    } else {
      // Connect first, then send
      connectVoice().then(() => {
        setTimeout(() => {
          if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
            setVoiceState("thinking");
            setStatusMessage("Awaaz is thinking...");
            socketRef.current.send(
              JSON.stringify({
                type: "text_turn",
                text,
                language,
              })
            );
          }
        }, 800);
      });
    }
  };

  const toggleLanguage = () => {
    const next = language === "ur-Latn" ? "en" : "ur-Latn";
    setLanguage(next);
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({ type: "set_language", language: next }));
    }
  };

  const samplePrompts = [
    "Show 1 Kanal villas in DHA Phase 2 under 8 Crore",
    "Calculate mortgage for 5 Crore with 20% down for 15 years",
    "Save this property to my shortlist",
    "Book a viewing visit for tomorrow",
  ];

  return (
    <div className="native-voice-studio">
      {/* Studio Top Control Strip */}
      <div className="studio-header-strip">
        <div className="studio-brand-badge">
          <div className={`status-orb-dot ${voiceState}`} />
          <span className="studio-brand-title">Awaaz AI Voice Concierge</span>
          <span className="studio-status-tag">{voiceState.toUpperCase()}</span>
        </div>

        <div className="studio-actions-right">
          <button
            type="button"
            className="lang-switcher-pill"
            onClick={toggleLanguage}
            title="Toggle between Urdu and English"
          >
            <span>{language === "ur-Latn" ? "Urdu (Roman)" : "English"}</span>
            <span className="lang-switch-arrow">⇄</span>
          </button>

          {voiceState !== "idle" && (
            <button
              type="button"
              className="end-session-pill"
              onClick={disconnect}
              title="End active voice session"
            >
              End Session
            </button>
          )}
        </div>
      </div>

      {/* Main Interactive Stage */}
      <div className="studio-stage">
        {/* Left Column: Visual Pulsing Orb & Voice Controls */}
        <div className="studio-orb-stage">
          <div className="orb-wrapper" onClick={connectVoice} role="button" tabIndex={0} aria-label="Toggle voice connection">
            <div
              className={`voice-dynamic-orb ${voiceState}`}
              style={{
                transform: `scale(${voiceState === "listening" || voiceState === "speaking" ? 1 + volumeLevel * 0.25 : 1})`,
              }}
            >
              <div className="orb-core" />
              <div className="orb-ring ring-1" />
              <div className="orb-ring ring-2" />
              <div className="orb-ring ring-3" />
            </div>

            <div className="orb-center-icon">
              <svg viewBox="0 0 24 24" width="34" height="34" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
                <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                <line x1="12" y1="19" x2="12" y2="22" />
              </svg>
            </div>
          </div>

          <p className="orb-action-caption">
            {voiceState === "idle"
              ? "Tap the Orb to Speak"
              : voiceState === "connecting"
              ? "Connecting..."
              : voiceState === "listening"
              ? "Listening to you..."
              : voiceState === "thinking"
              ? "Analyzing catalog..."
              : voiceState === "speaking"
              ? "Awaaz is speaking..."
              : "Tap to retry"}
          </p>

          <p className="orb-status-message">{statusMessage}</p>

          {/* Live Waveform Indicator */}
          <div className={`studio-waveform ${voiceState === "listening" || voiceState === "speaking" ? "active" : ""}`}>
            <span className="wave-bar wb-1" />
            <span className="wave-bar wb-2" />
            <span className="wave-bar wb-3" />
            <span className="wave-bar wb-4" />
            <span className="wave-bar wb-5" />
            <span className="wave-bar wb-6" />
            <span className="wave-bar wb-7" />
          </div>

          {/* Quick Voice Prompt Suggestions */}
          <div className="orb-suggestions">
            <span className="suggestions-title">Try asking:</span>
            <div className="suggestions-chips">
              {samplePrompts.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  className="suggestion-chip-btn"
                  onClick={() => handleSendText(prompt)}
                >
                  “{prompt}”
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Live Transcription Stream & Recommended Properties */}
        <div className="studio-stream-panel">
          <div className="stream-messages-scroll" ref={chatScrollRef}>
            {messages.length === 0 && !liveTranscript && (
              <div className="stream-empty-state">
                <div className="empty-chat-icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                  </svg>
                </div>
                <h3>Real-time Transcript Stream</h3>
                <p>
                  Start speaking or tap any sample question. Spoken words and verified property matches will appear here in real-time.
                </p>
              </div>
            )}

            {messages.map((msg) => (
              <div key={msg.id} className={`chat-bubble-row ${msg.sender}`}>
                <div className="chat-bubble">
                  <div className="chat-bubble-header">
                    <span className="chat-sender-name">{msg.sender === "user" ? "You" : "Awaaz AI"}</span>
                    <span className="chat-timestamp">{msg.timestamp}</span>
                  </div>
                  <p className="chat-text">{msg.text}</p>

                  {/* Inline Recommended Property Cards */}
                  {msg.properties && msg.properties.length > 0 && (
                    <div className="inline-properties-grid">
                      {msg.properties.map((property) => (
                        <div key={property.id} className="inline-property-card-wrap">
                          <ListingCard property={property} />
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Inline Executed Action Cards */}
                  {msg.actions && msg.actions.length > 0 && (
                    <div className="inline-actions-container">
                      {msg.actions.map((act) => (
                        <ActionCard key={act.id} action={act} />
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {/* Live streaming user utterance */}
            {liveTranscript && (
              <div className="chat-bubble-row user live">
                <div className="chat-bubble">
                  <div className="chat-bubble-header">
                    <span className="chat-sender-name">You (speaking...)</span>
                  </div>
                  <p className="chat-text live-text">{liveTranscript} <span className="typewriter-cursor">|</span></p>
                </div>
              </div>
            )}
          </div>

          {/* Fallback Text Input Bar */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendText();
            }}
            className="stream-input-bar"
          >
            <input
              type="text"
              value={textInput}
              onChange={(e) => setTextInput(e.target.value)}
              placeholder="Or type a question (e.g. 1 Kanal house in DHA)..."
              className="stream-text-input"
            />
            <button type="submit" className="stream-send-btn" aria-label="Send message">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2.5">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
