import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const source = await readFile(new URL("../src/voiceReplay.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText;
const { BoundedAudioReplay } = await import(
  `data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`
);

test("audio replay is available only after a complete provider response", () => {
  const replay = new BoundedAudioReplay();
  replay.append({ audio: "AAAA", encoding: "pcm_s16le", sampleRate: 24_000, isFinal: false });
  assert.equal(replay.canReplay, false);
  assert.deepEqual(replay.snapshot(), []);

  replay.append({ audio: "", encoding: "pcm_s16le", sampleRate: 24_000, isFinal: true });
  assert.equal(replay.canReplay, true);
  assert.equal(replay.snapshot().length, 1);
});

test("audio replay preserves MPEG finalization and resets between answers", () => {
  const replay = new BoundedAudioReplay();
  replay.append({ audio: "DATA", encoding: "audio/mpeg", sampleRate: 24_000, isFinal: false });
  replay.append({ audio: "", encoding: "audio/mpeg", sampleRate: 24_000, isFinal: true });
  assert.deepEqual(replay.snapshot().map((chunk) => chunk.isFinal), [false, true]);

  replay.reset();
  assert.equal(replay.canReplay, false);
  assert.deepEqual(replay.snapshot(), []);
});

test("audio replay discards partial audio when the memory cap is exceeded", () => {
  const replay = new BoundedAudioReplay(8);
  replay.append({ audio: "123456", encoding: "pcm_s16le", sampleRate: 24_000, isFinal: false });
  replay.append({ audio: "789", encoding: "pcm_s16le", sampleRate: 24_000, isFinal: true });
  assert.equal(replay.canReplay, false);
  assert.deepEqual(replay.snapshot(), []);
});

test("audio replay ignores malformed chunks and rejects invalid limits", () => {
  assert.throws(() => new BoundedAudioReplay(0), RangeError);
  const replay = new BoundedAudioReplay();
  replay.append({ audio: "DATA", encoding: "audio/wav", sampleRate: 24_000, isFinal: true });
  assert.equal(replay.canReplay, false);
});
