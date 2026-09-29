/** Block only on confirmed unavailability; unknown readiness is verified by the session API. */
export function resolveLiveVoiceAction(voiceReady: boolean | null): "connect" | "blocked" {
  return voiceReady === false ? "blocked" : "connect";
}

/** Recover briefly from network loss and backend restarts while the caller still wants voice. */
export function shouldAutoReconnectVoice(code: number, sessionRequested: boolean, attempts: number): boolean {
  return sessionRequested && attempts < 3 && (code === 1006 || code === 1012);
}

export function voiceReconnectDelayMs(attempt: number): number {
  return [500, 1_000, 2_000][Math.min(Math.max(Math.trunc(attempt), 1), 3) - 1];
}

/** Intentional stops must not let an old socket overwrite the next call's UI. */
export function closeVoiceSession(
  socket: Pick<WebSocket, "close" | "onopen" | "onclose" | "onerror" | "onmessage"> | null,
): void {
  if (!socket) return;
  socket.onopen = null;
  socket.onclose = null;
  socket.onerror = null;
  socket.onmessage = null;
  socket.close(1000, "User ended voice chat");
}

/** Ignore delayed audio/state from a response that the caller already interrupted. */
export class VoiceResponseTracker {
  private latest = 0;
  private interrupted = false;

  interrupt(): void { this.interrupted = true; }
  reset(): void { this.latest = 0; this.interrupted = false; }

  accept(event: { type: string; response_id?: number }): boolean {
    const id = event.response_id;
    if (id !== undefined) {
      if (id < this.latest) return false;
      if (id > this.latest) {
        this.latest = id;
        this.interrupted = false;
      }
    }
    const responseEvent = ["agent_response", "audio_chunk", "audio_unavailable", "agent_unavailable", "state"].includes(event.type);
    return !(this.interrupted && responseEvent);
  }
}

/** Keep a short leading buffer, then send only the active speech turn to manual STT. */
export class VoiceInputGate {
  private active = false;
  private leading: Uint8Array[] = [];
  private bytes = 0;
  constructor(private readonly maxLeadingBytes = 9600) {} // 300ms PCM16 at 16kHz

  start(): Uint8Array[] {
    this.active = true;
    const frames = this.leading;
    this.leading = [];
    this.bytes = 0;
    return frames;
  }
  end(): void { this.active = false; this.leading = []; this.bytes = 0; }
  push(frame: Uint8Array): Uint8Array[] {
    if (this.active) return [frame];
    const kept = frame.byteLength > this.maxLeadingBytes ? frame.slice(-this.maxLeadingBytes) : frame;
    this.leading.push(kept);
    this.bytes += kept.byteLength;
    while (this.bytes > this.maxLeadingBytes && this.leading.length > 1) {
      this.bytes -= this.leading.shift()!.byteLength;
    }
    return [];
  }
}
