export type ReplayChunk = {
  audio: string;
  encoding: "pcm_s16le" | "audio/mpeg";
  sampleRate: number;
  isFinal: boolean;
};

export interface ReplayPlaybackTarget {
  enqueueEncoded(audio: string, isFinal: boolean): void;
  playPcm16(audio: string, sampleRate: number): void;
  finish(): void;
}

export function enqueueReplay(chunks: readonly ReplayChunk[], playback: ReplayPlaybackTarget): void {
  for (const chunk of chunks) {
    if (chunk.encoding === "audio/mpeg") playback.enqueueEncoded(chunk.audio, chunk.isFinal);
    else playback.playPcm16(chunk.audio, chunk.sampleRate);
  }
  if (chunks.at(-1)?.encoding === "pcm_s16le") playback.finish();
}

const DEFAULT_MAX_AUDIO_CHARS = 8 * 1024 * 1024;

export class BoundedAudioReplay {
  private readonly maxAudioChars: number;
  private chunks: ReplayChunk[] = [];
  private audioChars = 0;
  private complete = false;
  private overflowed = false;

  constructor(maxAudioChars = DEFAULT_MAX_AUDIO_CHARS) {
    if (!Number.isSafeInteger(maxAudioChars) || maxAudioChars < 1) {
      throw new RangeError("maxAudioChars must be a positive safe integer");
    }
    this.maxAudioChars = maxAudioChars;
  }

  get canReplay(): boolean {
    return this.complete
      && !this.overflowed
      && this.chunks.some((chunk) => chunk.audio.length > 0);
  }

  reset(): void {
    this.chunks = [];
    this.audioChars = 0;
    this.complete = false;
    this.overflowed = false;
  }

  append(chunk: ReplayChunk): void {
    if (
      (chunk.encoding !== "pcm_s16le" && chunk.encoding !== "audio/mpeg")
      || !Number.isInteger(chunk.sampleRate)
      || chunk.sampleRate < 8_000
      || chunk.sampleRate > 96_000
      || typeof chunk.audio !== "string"
      || typeof chunk.isFinal !== "boolean"
    ) {
      return;
    }

    if (this.overflowed) {
      this.complete ||= chunk.isFinal;
      return;
    }
    if (this.audioChars + chunk.audio.length > this.maxAudioChars) {
      this.chunks = [];
      this.overflowed = true;
      this.complete ||= chunk.isFinal;
      return;
    }
    if (chunk.audio) {
      this.chunks.push({ ...chunk });
      this.audioChars += chunk.audio.length;
    } else if (
      chunk.encoding === "audio/mpeg"
      && chunk.isFinal
      && this.chunks.length > 0
    ) {
      // Preserve the empty final marker required to flush buffered MPEG playback.
      this.chunks.push({ ...chunk });
    }
    this.complete ||= chunk.isFinal;
  }

  snapshot(): ReplayChunk[] {
    return this.canReplay ? this.chunks.map((chunk) => ({ ...chunk })) : [];
  }
}
