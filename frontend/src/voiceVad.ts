export type VoiceActivityTransition = "speech_started" | "speech_ended";

/** Small adaptive RMS detector for browser microphone turn boundaries. */
export class VoiceActivityDetector {
  private noiseFloor = 0.002;
  private calibrationMs = 0;
  private speechActive = false;
  private silenceMs = 0;
  private speechMs = 0;

  constructor(
    private readonly endSilenceMs = 650,
    private readonly maxTurnMs = 20_000,
  ) {}

  process(rms: number, frameMs: number): VoiceActivityTransition | null {
    if (!Number.isFinite(rms) || rms < 0 || !Number.isFinite(frameMs) || frameMs <= 0) {
      return null;
    }

    if (!this.speechActive) {
      if (this.calibrationMs < 300 && rms < 0.02) {
        this.noiseFloor = Math.max(0.0001, this.noiseFloor * 0.9 + rms * 0.1);
        this.calibrationMs += frameMs;
        if (this.calibrationMs < 300) return null;
      }
      const startThreshold = Math.max(0.0045, this.noiseFloor * 2.2);
      if (rms >= startThreshold) {
        this.speechActive = true;
        this.silenceMs = 0;
        this.speechMs = frameMs;
        return "speech_started";
      }
      this.noiseFloor = Math.max(0.0001, this.noiseFloor * 0.9 + rms * 0.1);
      return null;
    }

    const endThreshold = Math.max(0.003, this.noiseFloor * 1.6);
    this.speechMs += frameMs;
    this.silenceMs = rms < endThreshold ? this.silenceMs + frameMs : 0;
    if (this.silenceMs >= this.endSilenceMs || this.speechMs >= this.maxTurnMs) {
      this.speechActive = false;
      this.silenceMs = 0;
      this.speechMs = 0;
      return "speech_ended";
    }
    return null;
  }

  reset(): void {
    this.noiseFloor = 0.002;
    this.calibrationMs = 0;
    this.speechActive = false;
    this.silenceMs = 0;
    this.speechMs = 0;
  }
}
