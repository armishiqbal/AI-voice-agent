export type AudioChunkHandler = (chunk: Uint8Array) => void;
import { VoiceActivityDetector } from "./voiceVad";
import captureWorkletUrl from "./pcmCaptureWorklet.js?url";

function resampleTo16k(input: Float32Array, inputRate: number): Int16Array {
  if (inputRate === 16_000) {
    return Float32ToInt16(input);
  }
  const ratio = inputRate / 16_000;
  const output = new Int16Array(Math.max(1, Math.floor(input.length / ratio)));
  for (let index = 0; index < output.length; index += 1) {
    const sourceIndex = index * ratio;
    const left = Math.floor(sourceIndex);
    const right = Math.min(left + 1, input.length - 1);
    const amount = sourceIndex - left;
    const sample = input[left] * (1 - amount) + input[right] * amount;
    output[index] = Math.max(-1, Math.min(1, sample)) * 0x7fff;
  }
  return output;
}

function Float32ToInt16(input: Float32Array): Int16Array {
  const output = new Int16Array(input.length);
  for (let index = 0; index < input.length; index += 1) {
    output[index] = Math.max(-1, Math.min(1, input[index])) * 0x7fff;
  }
  return output;
}

export class BrowserAudioCapture {
  private context: AudioContext | null = null;
  private stream: MediaStream | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private processor: AudioWorkletNode | null = null;
  private sink: GainNode | null = null;
  private firstFrameTimer: ReturnType<typeof setTimeout> | null = null;
  private stopped = false;
  private readonly voiceActivity = new VoiceActivityDetector();
  private analyser: AnalyserNode | null = null;

  getAnalyser(): AnalyserNode | null {
    return this.analyser;
  }

  async start(
    onChunk: AudioChunkHandler,
    onReady: () => void,
    turnHandlers?: { onSpeechStart: () => void; onSpeechEnd: () => void; onLevel?: (rms: number, frameMs: number) => void; onCaptureStalled?: () => void },
    deviceId?: string,
  ): Promise<void> {
    this.stopped = false;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          ...(deviceId ? { deviceId: { exact: deviceId } } : {}),
        },
      });
      if (this.stopped) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      this.stream = stream;
      const context = new AudioContext();
      this.context = context;
      await context.resume();
      if (this.stopped) return;
      if (!context.audioWorklet) throw new Error("This browser does not support AudioWorklet");
      await context.audioWorklet.addModule(captureWorkletUrl);
      if (this.stopped) return;
      this.source = context.createMediaStreamSource(stream);
      this.analyser = context.createAnalyser();
      this.analyser.fftSize = 128;
      this.source.connect(this.analyser);
      this.processor = new AudioWorkletNode(context, "pcm-capture-processor", {
        numberOfInputs: 1,
        numberOfOutputs: 1,
        outputChannelCount: [1],
      });
      this.sink = context.createGain();
      this.sink.gain.value = 0;
      const captureStalled = () => {
        if (this.stopped) return;
        turnHandlers?.onCaptureStalled?.();
        this.stop();
      };
      this.processor.onprocessorerror = captureStalled;
      this.processor.port.onmessage = (event: MessageEvent<Float32Array>) => {
        if (this.stopped || !(event.data instanceof Float32Array)) return;
        if (this.firstFrameTimer !== null) {
          clearTimeout(this.firstFrameTimer);
          this.firstFrameTimer = null;
        }
        const pcm = resampleTo16k(event.data, context.sampleRate);
        if (turnHandlers) {
          let energy = 0;
          for (let index = 0; index < pcm.length; index += 1) {
            const sample = pcm[index] / 32768;
            energy += sample * sample;
          }
          const rms = Math.sqrt(energy / Math.max(1, pcm.length));
          const frameMs = pcm.length * 1000 / 16_000;
          turnHandlers.onLevel?.(rms, frameMs);
          const transition = this.voiceActivity.process(rms, frameMs);
          if (transition === "speech_started") turnHandlers.onSpeechStart();
          if (transition === "speech_ended") turnHandlers.onSpeechEnd();
        }
        onChunk(new Uint8Array(pcm.buffer));
      };
      this.processor.connect(this.sink);
      this.sink.connect(context.destination);
      onReady();
      if (this.stopped) return;
      this.firstFrameTimer = setTimeout(captureStalled, 3_000);
      this.source.connect(this.processor);
    } catch (error) {
      if (this.stopped) return;
      this.stop();
      throw error;
    }
  }

  stop(): void {
    this.stopped = true;
    if (this.firstFrameTimer !== null) clearTimeout(this.firstFrameTimer);
    this.firstFrameTimer = null;
    this.voiceActivity.reset();
    this.processor?.port.postMessage({ type: "stop" });
    if (this.processor) this.processor.port.onmessage = null;
    this.processor?.disconnect();
    this.analyser?.disconnect();
    this.source?.disconnect();
    this.sink?.disconnect();
    this.stream?.getTracks().forEach((track) => track.stop());
    void this.context?.close();
    this.analyser = null;
    this.processor = null;
    this.source = null;
    this.sink = null;
    this.stream = null;
    this.context = null;
  }
}

export class BrowserAudioPlayback {
  private context: AudioContext | null = null;
  private cursor = 0;
  private sources = new Set<AudioBufferSourceNode>();
  private encodedChunks: Uint8Array[] = [];
  private mediaSource: MediaSource | null = null;
  private mediaUrl: string | null = null;
  private mediaAudio: HTMLAudioElement | null = null;
  private mediaBuffer: SourceBuffer | null = null;
  private mediaQueue: Uint8Array[] = [];
  private mediaFinalRequested = false;
  private analyser: AnalyserNode | null = null;

  getAnalyser(): AnalyserNode | null {
    return this.analyser;
  }

  async activate(): Promise<void> {
    await this.ensureContext().resume();
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

  playPcm16(base64: string, sampleRate: number): void {
    const context = this.ensureContext();
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
    const samples = new Int16Array(bytes.buffer);
    const buffer = context.createBuffer(1, samples.length, sampleRate);
    const channel = buffer.getChannelData(0);
    for (let index = 0; index < samples.length; index += 1) channel[index] = samples[index] / 0x7fff;
    const source = context.createBufferSource();
    source.buffer = buffer;
    source.connect(this.analyser || context.destination);
    const start = Math.max(context.currentTime, this.cursor);
    source.start(start);
    this.cursor = start + buffer.duration;
    this.sources.add(source);
    source.onended = () => this.sources.delete(source);
  }

  enqueueEncoded(base64: string, isFinal: boolean): void {
    if (base64) {
      const binary = atob(base64);
      const bytes = new Uint8Array(binary.length);
      for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
      if (typeof MediaSource !== "undefined" && MediaSource.isTypeSupported("audio/mpeg")) {
        this.startMediaStream();
        this.mediaQueue.push(bytes);
        this.flushMediaStream();
      } else {
        this.encodedChunks.push(bytes);
      }
    }
    if (this.mediaSource) {
      this.mediaFinalRequested ||= isFinal;
      this.flushMediaStream();
      return;
    }
    if (!isFinal || this.encodedChunks.length === 0) return;
    const total = this.encodedChunks.reduce((sum, item) => sum + item.byteLength, 0);
    const merged = new Uint8Array(total);
    let offset = 0;
    for (const item of this.encodedChunks) {
      merged.set(item, offset);
      offset += item.byteLength;
    }
    this.encodedChunks = [];
    void this.ensureContext().decodeAudioData(merged.buffer.slice(0)).then((buffer) => {
      const source = this.ensureContext().createBufferSource();
      source.buffer = buffer;
      source.connect(this.analyser || this.ensureContext().destination);
      const start = Math.max(this.ensureContext().currentTime, this.cursor);
      source.start(start);
      this.cursor = start + buffer.duration;
      this.sources.add(source);
      source.onended = () => this.sources.delete(source);
    }).catch(() => undefined);
  }

  private startMediaStream(): void {
    if (this.mediaSource) return;
    this.mediaSource = new MediaSource();
    this.mediaUrl = URL.createObjectURL(this.mediaSource);
    this.mediaAudio = new Audio(this.mediaUrl);
    this.mediaAudio.autoplay = true;
    this.mediaSource.addEventListener("sourceopen", () => {
      if (!this.mediaSource || this.mediaBuffer) return;
      this.mediaBuffer = this.mediaSource.addSourceBuffer("audio/mpeg");
      this.mediaBuffer.addEventListener("updateend", () => this.flushMediaStream());
      this.flushMediaStream();
    }, { once: true });
    void this.mediaAudio.play().catch(() => undefined);
  }

  private flushMediaStream(): void {
    if (!this.mediaSource || !this.mediaBuffer || this.mediaBuffer.updating) return;
    if (this.mediaQueue.length) {
      const chunk = this.mediaQueue.shift();
      if (chunk) {
        const buffer = chunk.buffer.slice(chunk.byteOffset, chunk.byteOffset + chunk.byteLength);
        this.mediaBuffer.appendBuffer(buffer);
      }
      return;
    }
    if (this.mediaFinalRequested && this.mediaSource.readyState === "open") {
      this.mediaSource.endOfStream();
    }
  }

  stop(): void {
    this.sources.forEach((source) => source.stop());
    this.sources.clear();
    this.cursor = 0;
    this.encodedChunks = [];
    this.mediaQueue = [];
    this.mediaFinalRequested = false;
    this.mediaAudio?.pause();
    if (this.mediaAudio) {
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
