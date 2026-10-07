"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ASSISTANT_MESSAGE_MAX_LENGTH,
  createHelloMessage,
  createSubmitTextMessage,
  hasTrustedMessageOriginAndSource,
  parseFrameMessage,
  parseActionMessage,
  type AssistantPhase,
} from "@/lib/assistantBridge";
import { addToShortlist, removeFromShortlist } from "@/lib/favorites";
import { ActionCard, type ChatAction } from "@/components/ActionCard";

interface LuxuryVoiceStudioClientProps {
  assistantUrl?: string;
}

const exampleQuestions = [
  {
    label: "Buy in Islamabad",
    text: "I want to buy a home in Islamabad. Ask me about my preferred area, property type, and budget in PKR, then search published listings.",
  },
  {
    label: "Find a rental",
    text: "I am looking to rent a two-bedroom apartment in Islamabad or Rawalpindi. Ask me which area and monthly budget I prefer, then search published listings.",
  },
  {
    label: "Explore an area",
    text: "Help me compare F-10 and G-11 in Islamabad for a family home. Ask what matters to me, then use the available area information.",
  },
  {
    label: "Estimate installments",
    text: "Estimate installments for a property costing PKR 5 crore with a 20 percent down payment over 15 years.",
  },
];

const phaseLabels: Record<AssistantPhase, string> = {
  idle: "Ready. Choose a prompt, type a question, or start voice in the assistant below.",
  connecting: "Connecting to voice service",
  listening: "Listening",
  transcribing: "Transcribing your request",
  thinking: "Working on your question",
  speaking: "Awaaz is speaking",
  error: "Voice needs attention. You can still type a question.",
};

export function LuxuryVoiceStudioClient({ assistantUrl }: LuxuryVoiceStudioClientProps) {
  const router = useRouter();
  const [assistantReady, setAssistantReady] = useState(false);
  const [frameTimedOut, setFrameTimedOut] = useState(false);
  const [phase, setPhase] = useState<AssistantPhase>("idle");
  const [statusMessage, setStatusMessage] = useState("Loading the assistant…");
  const [iframeKey, setIframeKey] = useState(0);
  const [executedActions, setExecutedActions] = useState<ChatAction[]>([]);

  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const assistantOriginRef = useRef<string | null>(null);
  const assistantReadyRef = useRef(false);
  const pendingQuestionRef = useRef<string | null>(null);

  useEffect(() => {
    setIframeKey(Date.now());
  }, []);

  const resolvedAssistantUrl = assistantUrl || "http://127.0.0.1:8000/assistant/";
  const assistantFrameUrl = `${resolvedAssistantUrl}${resolvedAssistantUrl.includes("?") ? "&" : "?"}awaazFrame=${iframeKey}`;

  const postQuestionToAssistant = useCallback((text: string) => {
    const frame = iframeRef.current as HTMLIFrameElement | null;
    const targetOrigin = assistantOriginRef.current;
    if (!frame?.contentWindow || !targetOrigin) return false;
    frame.contentWindow.postMessage(createSubmitTextMessage(text), targetOrigin);
    return true;
  }, []);

  useEffect(() => {
    let expectedOrigin: string;
    try {
      expectedOrigin = new URL(resolvedAssistantUrl, window.location.href).origin;
    } catch {
      setStatusMessage("The assistant address is invalid. Check the website configuration.");
      return;
    }
    assistantOriginRef.current = expectedOrigin;

    const readyTimer = window.setTimeout(() => {
      if (!assistantReadyRef.current) {
        setFrameTimedOut(true);
        setStatusMessage("The assistant is taking too long to load. Retry or open it in a new window.");
        window.clearInterval(handshakeInterval);
      }
    }, 12_000);

    const sendHandshake = () => {
      if (!assistantReadyRef.current) {
        const frame = iframeRef.current as HTMLIFrameElement | null;
        frame?.contentWindow?.postMessage(createHelloMessage(), expectedOrigin);
      }
    };
    sendHandshake();
    const handshakeInterval = window.setInterval(sendHandshake, 500);

    const handleAssistantMessage = (event: MessageEvent<unknown>) => {
      const frame = iframeRef.current as HTMLIFrameElement | null;
      if (!frame?.contentWindow
        || !hasTrustedMessageOriginAndSource(event, frame.contentWindow, [expectedOrigin])) return;

      // 1. Process Frame Status Message (ready, state)
      const frameMessage = parseFrameMessage(event.data);
      if (frameMessage) {
        setPhase(frameMessage.phase);
        setStatusMessage(phaseLabels[frameMessage.phase]);
        if (frameMessage.type === "ready") {
          assistantReadyRef.current = true;
          setAssistantReady(true);
          setFrameTimedOut(false);
          window.clearTimeout(readyTimer);
          window.clearInterval(handshakeInterval);
          const pendingQuestion = pendingQuestionRef.current;
          if (pendingQuestion && postQuestionToAssistant(pendingQuestion)) {
            pendingQuestionRef.current = null;
            setFrameTimedOut(false);
            setStatusMessage("Your question was sent. Follow the reply in the conversation below.");
          }
        }
      }

      // 2. Process Autonomous Action Executed Message
      const actionMessage = parseActionMessage(event.data);
      if (actionMessage && actionMessage.action) {
        const act = actionMessage.action;
        const newChatAction: ChatAction = {
          id: act.id || `act-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
          kind: act.kind,
          payload: (act.payload || {}) as Record<string, unknown>,
          summary: act.summary || "",
          status: "executed",
        };

        setExecutedActions((prev) => [newChatAction, ...prev.filter((a) => a.id !== newChatAction.id).slice(0, 4)]);

        // Live Action Execution on the Parent Next.js Site
        if (act.kind === "shortlist_property") {
          const propId = String(act.payload?.property_id || "").toLowerCase();
          if (propId) {
            if (act.payload?.action === "remove") {
              removeFromShortlist(propId);
            } else {
              addToShortlist(propId);
            }
          }
        } else if (act.kind === "navigate_to") {
          const path = String(act.payload?.path || "");
          if (path) {
            setTimeout(() => {
              router.push(path);
            }, 1200);
          }
        }
      }
    };

    window.addEventListener("message", handleAssistantMessage);
    return () => {
      window.clearTimeout(readyTimer);
      window.clearInterval(handshakeInterval);
      window.removeEventListener("message", handleAssistantMessage);
      assistantReadyRef.current = false;
    };
  }, [iframeKey, postQuestionToAssistant, resolvedAssistantUrl, router]);

  const askAssistant = (rawText: string) => {
    const text = rawText.trim();
    if (!text) return;
    if (text.length > ASSISTANT_MESSAGE_MAX_LENGTH) {
      setStatusMessage(`Please keep your question to ${ASSISTANT_MESSAGE_MAX_LENGTH} characters or fewer.`);
      return;
    }

    if (!assistantReadyRef.current) {
      if (!pendingQuestionRef.current) {
        pendingQuestionRef.current = text;
        setStatusMessage("The assistant is loading. Your question will be sent when it is ready.");
      } else {
        setStatusMessage("Your first question is still waiting to send. Please wait a moment.");
      }
      return;
    }

    if (postQuestionToAssistant(text)) {
      setStatusMessage("Your question was sent. Follow the reply in the conversation below.");
    } else {
      assistantReadyRef.current = false;
      setAssistantReady(false);
      pendingQuestionRef.current = text;
      setStatusMessage("The assistant is reconnecting. Your question will be sent when it is ready.");
    }
  };

  const handleRestart = () => {
    assistantReadyRef.current = false;
    setAssistantReady(false);
    setFrameTimedOut(false);
    setPhase("idle");
    setStatusMessage("Restarting the assistant…");
    setIframeKey((current) => current + 1);
  };

  return (
    <div className="voice-studio-theater-wrapper">
      <section className="assistant-quick-start" aria-labelledby="assistant-quick-start-title">
        <div className="assistant-quick-start-copy">
          <p className="assistant-quick-start-eyebrow">Start with a question</p>
          <h2 id="assistant-quick-start-title">Start with the kind of move you have in mind.</h2>
          <p>Give Awaaz a starting point. You can refine the area, budget, and property details in the conversation.</p>
        </div>

        <div className="assistant-example-questions" role="group" aria-label="Example questions">
          {exampleQuestions.map((example) => (
            <button
              key={example.label}
              type="button"
              className="assistant-example-question"
              onClick={() => askAssistant(example.text)}
            >
              {example.label}<span aria-hidden="true">→</span>
            </button>
          ))}
        </div>
        <p className="assistant-bridge-status" role="status" aria-live="polite" aria-atomic="true">
          <span className={`assistant-status-dot phase-${phase}`} aria-hidden="true" />
          {statusMessage}
        </p>
      </section>

      {/* Actions taken at the user’s request */}
      {executedActions.length > 0 && (
        <section className="voice-studio-actions-feed" aria-label="Autonomous Actions Executed">
          <div className="actions-feed-header">
            <span className="actions-feed-badge">
              <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                <path d="m9 12 2 2 4-4" />
              </svg>
              Assistant actions ({executedActions.length})
            </span>
            <button
              type="button"
              onClick={() => setExecutedActions([])}
              className="actions-feed-clear-btn"
            >
              Clear Feed
            </button>
          </div>

          <div className="actions-feed-list">
            {executedActions.map((act) => (
              <ActionCard
                key={act.id}
                action={act}
                onUndo={(id) => {
                  setExecutedActions((prev) =>
                    prev.map((a) => (a.id === id ? { ...a, status: "undone" } : a))
                  );
                }}
              />
            ))}
          </div>
        </section>
      )}

      <div className="studio-bezel-topbar" id="voice-console">
        <div className="bezel-left">
          <div className="status-live-indicator">
            <span className={`live-glow-dot phase-${phase}`} aria-hidden="true" />
            <span className="status-title">Awaaz voice assistant</span>
          </div>
          <span className="bezel-telemetry-pill">Voice and text assistance</span>
          <span className="bezel-lang-pill">Urdu · English · Roman Urdu</span>
        </div>

        <div className="bezel-right">
          <button
            type="button"
            className="bezel-tool-btn"
            onClick={handleRestart}
            title="Restart the assistant"
          >
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" />
              <path d="M21 3v5h-5" />
              <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" />
              <path d="M8 16H3v5" />
            </svg>
            <span>Restart</span>
          </button>
          <a
            href={resolvedAssistantUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="bezel-tool-btn launch-btn"
            title="Open the assistant in a new window"
          >
            <span>Open separately</span>
            <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
              <polyline points="15 3 21 3 21 9" />
              <line x1="10" y1="14" x2="21" y2="3" />
            </svg>
          </a>
        </div>
      </div>

      <div className="studio-canvas-stage">
        <iframe
          key={iframeKey}
          ref={iframeRef}
          src={assistantFrameUrl}
          title="Awaaz Estate voice and text assistant"
          className="studio-canvas-iframe studio-iframe"
          allow="microphone"
          referrerPolicy="origin"
          loading="eager"
        />
        {!assistantReady && !frameTimedOut && (
          <div className="assistant-frame-loading" role="status" aria-live="polite">
            <span className="assistant-frame-spinner" />
            <span>{statusMessage}</span>
          </div>
        )}
        {!assistantReady && frameTimedOut && (
          <div className="assistant-frame-timeout" role="alert">
            <div className="assistant-frame-timeout-mark" aria-hidden="true">!</div>
            <h2>The assistant is taking longer than expected</h2>
            <p>Your question will stay on this page. Try reconnecting, or open the assistant directly.</p>
            <div className="assistant-frame-timeout-actions">
              <button type="button" className="button" onClick={handleRestart}>Reconnect</button>
              <a className="button secondary" href={resolvedAssistantUrl} target="_blank" rel="noopener noreferrer">Open assistant</a>
              <a className="assistant-frame-browse" href="/properties">Browse listings</a>
            </div>
          </div>
        )}
      </div>

      <div className="studio-bezel-bottombar">
        <div className="bottombar-left">
          <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
          <span>Microphone access is requested only when you start voice chat. Text questions do not need microphone access.</span>
        </div>
        <div className="bottombar-right">
          <span>Prefer browsing?</span>
          <a href="/properties" className="catalog-text-link">Explore properties →</a>
        </div>
      </div>
    </div>
  );
}
