export interface PlaybackHandlers {
  onStart?: () => void;
  onDrain?: () => void;
  onError?: (error: Error) => void;
}
const PREBUFFER_SECONDS = 0.08;
const MAX_QUEUED_SECONDS = 60;
const MAX_ENCODED_BYTES = 16 * 1024 * 1024;

/** A generation prevents cancelled, asynchronously decoded audio from playing later. */
export class BrowserAudioPlayback {
  private context: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private cursor = 0;
  private sources = new Set<AudioBufferSourceNode>();
  private generation = 0;
  private pendingDecodes = 0;
  private finalRequested = false;
  private started = false;
  private startTimer: ReturnType<typeof setTimeout> | null = null;
  private handlers: PlaybackHandlers;
  private encodedChunks: Uint8Array[] = [];
  private encodedBytes = 0;
  private mediaSource: MediaSource | null = null;
  private mediaUrl: string | null = null;
  private mediaAudio: HTMLAudioElement | null = null;
  private mediaBuffer: SourceBuffer | null = null;
  private mediaQueue: Uint8Array[] = [];
  private mediaEnded = false;

  constructor(handlers: PlaybackHandlers = {}) { this.handlers = handlers; }
  setHandlers(handlers: PlaybackHandlers): void { this.handlers = handlers; }
  getAnalyser(): AnalyserNode | null { return this.analyser; }
  async activate(): Promise<void> {
    const context = this.ensureContext();
    await context.resume();
    if (context.state !== "running") throw new Error("Audio playback is blocked. Click the microphone to enable sound.");
  }
  private ensureContext(): AudioContext {
    if (!this.context) {
      this.context = new AudioContext();
      this.analyser = this.context.createAnalyser();
      this.analyser.fftSize = 128;
      this.analyser.connect(this.context.destination);
    }
    return this.context;
  }
  private fail(error: unknown): void {
    this.stop();
    this.handlers.onError?.(error instanceof Error ? error : new Error(String(error)));
  }
  private decodeBase64(base64: string): Uint8Array {
    if (base64.length > MAX_ENCODED_BYTES * 4 / 3 + 4) throw new Error("Audio packet exceeded the playback limit.");
    return Uint8Array.from(atob(base64), (char) => char.charCodeAt(0));
  }
  playPcm16(base64: string, sampleRate: number): void {
    try {
      if (!Number.isInteger(sampleRate) || sampleRate < 8_000 || sampleRate > 96_000) throw new Error("Invalid audio sample rate.");
      const bytes = this.decodeBase64(base64);
      if (!bytes.length) return;
      if (bytes.length % 2) throw new Error("Incomplete PCM audio sample.");
      const context = this.ensureContext();
      const buffer = context.createBuffer(1, bytes.length / 2, sampleRate);
      const channel = buffer.getChannelData(0);
      const view = new DataView(bytes.buffer);
      for (let i = 0; i < channel.length; i += 1) channel[i] = view.getInt16(i * 2, true) / 32768;
      this.schedule(buffer);
    } catch (error) { this.fail(error); }
  }
  private schedule(buffer: AudioBuffer): void {
    const context = this.ensureContext();
    if (context.state !== "running") throw new Error("Audio playback is suspended. Click the microphone to enable sound.");
    // Buffer startup/starvation only; contiguous chunks remain gapless.
    const start = this.cursor > context.currentTime ? this.cursor : context.currentTime + PREBUFFER_SECONDS;
    if (start + buffer.duration - context.currentTime > MAX_QUEUED_SECONDS) throw new Error("Audio playback fell too far behind. Please retry.");
    const generation = this.generation;
    const source = context.createBufferSource();
    source.buffer = buffer;
    source.connect(this.analyser || context.destination);
    source.onended = () => {
      source.disconnect();
      if (generation !== this.generation) return;
      this.sources.delete(source);
      this.checkDrain();
    };
    this.sources.add(source);
    source.start(start);
    this.cursor = start + buffer.duration;
    if (!this.started && this.startTimer === null) {
      this.startTimer = setTimeout(() => {
        this.startTimer = null;
        if (generation === this.generation) this.markStarted();
      }, Math.max(0, (start - context.currentTime) * 1000));
    }
  }
  private markStarted(): void {
    if (this.started) return;
    this.started = true;
    this.handlers.onStart?.();
  }
  enqueueEncoded(base64: string, isFinal: boolean): void {
    try {
      if (base64) {
        const bytes = this.decodeBase64(base64);
        this.encodedBytes += bytes.length;
        if (this.encodedBytes > MAX_ENCODED_BYTES) throw new Error("Encoded audio exceeded the playback limit.");
        if (typeof MediaSource !== "undefined" && MediaSource.isTypeSupported("audio/mpeg")) {
          this.startMediaStream();
          this.mediaQueue.push(bytes);
          this.flushMediaStream();
        } else this.encodedChunks.push(bytes);
      }
      if (isFinal) this.finish();
    } catch (error) { this.fail(error); }
  }
  /** Server completion is not playback completion: onDrain waits for the last sample. */
  finish(): void {
    if (this.finalRequested) return;
    this.finalRequested = true;
    if (this.mediaSource) { this.flushMediaStream(); return; }
    if (this.encodedChunks.length) {
      const merged = new Uint8Array(this.encodedChunks.reduce((sum, chunk) => sum + chunk.length, 0));
      let offset = 0;
      for (const chunk of this.encodedChunks) { merged.set(chunk, offset); offset += chunk.length; }
      this.encodedChunks = [];
      const generation = this.generation;
      this.pendingDecodes += 1;
      void this.ensureContext().decodeAudioData(merged.buffer).then((buffer) => {
        if (generation !== this.generation) return;
        this.pendingDecodes -= 1;
        this.schedule(buffer);
        this.checkDrain();
      }).catch((error: unknown) => { if (generation === this.generation) this.fail(error); });
    }
    this.checkDrain();
  }
  private checkDrain(): void {
    if (!this.finalRequested || this.sources.size || this.pendingDecodes || (this.mediaSource && !this.mediaEnded)) return;
    this.stop();
    this.handlers.onDrain?.();
  }
  private startMediaStream(): void {
    if (this.mediaSource) return;
    const generation = this.generation;
    const mediaSource = new MediaSource();
    this.mediaSource = mediaSource;
    this.mediaUrl = URL.createObjectURL(mediaSource);
    const audio = new Audio(this.mediaUrl);
    this.mediaAudio = audio;
    audio.onplaying = () => { if (generation === this.generation) this.markStarted(); };
    audio.onended = () => {
      if (generation !== this.generation) return;
      this.mediaEnded = true;
      this.checkDrain();
    };
    audio.onerror = () => { if (generation === this.generation) this.fail(new Error("The browser could not decode the voice response.")); };
    mediaSource.addEventListener("sourceopen", () => {
      if (generation !== this.generation || this.mediaBuffer) return;
      try {
        this.mediaBuffer = mediaSource.addSourceBuffer("audio/mpeg");
        this.mediaBuffer.addEventListener("updateend", () => { if (generation === this.generation) this.flushMediaStream(); });
        this.mediaBuffer.addEventListener("error", () => { if (generation === this.generation) this.fail(new Error("Voice audio stream decoding failed.")); });
        this.flushMediaStream();
      } catch (error) { this.fail(error); }
    }, { once: true });
    void audio.play().catch((error: unknown) => { if (generation === this.generation) this.fail(error); });
  }
  private flushMediaStream(): void {
    if (!this.mediaSource || !this.mediaBuffer || this.mediaBuffer.updating) return;
    try {
      const cutoff = (this.mediaAudio?.currentTime ?? 0) - 5;
      if (cutoff > 0 && this.mediaBuffer.buffered.length && this.mediaBuffer.buffered.start(0) < cutoff) {
        this.mediaBuffer.remove(0, cutoff);
        return;
      }
      const chunk = this.mediaQueue.shift();
      if (chunk) { this.mediaBuffer.appendBuffer(chunk.buffer.slice(chunk.byteOffset, chunk.byteOffset + chunk.byteLength)); return; }
      if (this.finalRequested && this.mediaSource.readyState === "open") this.mediaSource.endOfStream();
    } catch (error) { this.fail(error); }
  }
  stop(): void {
    this.generation += 1;
    if (this.startTimer !== null) clearTimeout(this.startTimer);
    this.startTimer = null;
    this.sources.forEach((source) => { source.onended = null; try { source.stop(); } catch { /* Already ended. */ } source.disconnect(); });
    this.sources.clear();
    this.cursor = 0;
    this.pendingDecodes = 0;
    this.finalRequested = false;
    this.started = false;
    this.encodedBytes = 0;
    this.encodedChunks = [];
    this.mediaQueue = [];
    this.mediaEnded = false;
    if (this.mediaAudio) {
      this.mediaAudio.onplaying = null;
      this.mediaAudio.onended = null;
      this.mediaAudio.onerror = null;
      this.mediaAudio.pause();
      this.mediaAudio.removeAttribute("src");
      this.mediaAudio.load();
    }
    if (this.mediaUrl) URL.revokeObjectURL(this.mediaUrl);
    this.mediaSource = null;
    this.mediaUrl = null;
    this.mediaAudio = null;
    this.mediaBuffer = null;
  }
}
