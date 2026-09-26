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
  private lastFrameAt = 0;
  private stallTimer: ReturnType<typeof setInterval> | null = null;
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
      stream.getAudioTracks().forEach((track) => { track.onended = captureStalled; });
      this.lastFrameAt = performance.now();
      this.stallTimer = setInterval(() => {
        if (performance.now() - this.lastFrameAt > 5_000) captureStalled();
      }, 1_000);
      this.processor.port.onmessage = (event: MessageEvent<Float32Array>) => {
        if (this.stopped || !(event.data instanceof Float32Array)) return;
        if (this.firstFrameTimer !== null) {
          clearTimeout(this.firstFrameTimer);
          this.firstFrameTimer = null;
        }
        this.lastFrameAt = performance.now();
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
    if (this.stallTimer !== null) clearInterval(this.stallTimer);
    this.stallTimer = null;
    this.voiceActivity.reset();
    this.processor?.port.postMessage({ type: "stop" });
    if (this.processor) this.processor.port.onmessage = null;
    this.processor?.disconnect();
    this.analyser?.disconnect();
    this.source?.disconnect();
    this.sink?.disconnect();
    this.stream?.getTracks().forEach((track) => { track.onended = null; track.stop(); });
    void this.context?.close();
    this.analyser = null;
    this.processor = null;
    this.source = null;
    this.sink = null;
    this.stream = null;
    this.context = null;
  }
}

export { BrowserAudioPlayback } from "./voicePlayback";
