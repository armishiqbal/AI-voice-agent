import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const source = await readFile(new URL("../src/voicePlayback.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText;
const { BrowserAudioPlayback } = await import(
  `data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`
);

function installAudioContext() {
  const scheduled = [];
  const timers = [];
  const sources = [];
  let decodeResolve;
  class FakeAudioContext {
    currentTime = 10;
    state = "running";
    destination = {};
    createAnalyser() { return { fftSize: 0, connect() {} }; }
    createBuffer(_channels, length, sampleRate) {
      const samples = new Float32Array(length);
      return {
        duration: length / sampleRate,
        sampleRate,
        getChannelData: () => samples,
      };
    }
    createBufferSource() {
      const source = {
        buffer: null,
        onended: null,
        connect() {},
        disconnect() {},
        start: (time) => scheduled.push(time),
        stop() {},
        end() { this.onended?.(); },
      };
      sources.push(source);
      return source;
    }
    decodeAudioData() {
      return new Promise((resolve) => { decodeResolve = resolve; });
    }
    async resume() {}
  }
  const oldAudioContext = globalThis.AudioContext;
  const oldSetTimeout = globalThis.setTimeout;
  const oldClearTimeout = globalThis.clearTimeout;
  globalThis.AudioContext = FakeAudioContext;
  globalThis.setTimeout = (callback) => { timers.push(callback); return timers.length; };
  globalThis.clearTimeout = () => {};
  return {
    scheduled,
    sources,
    timers,
    resolveDecode(buffer) { decodeResolve?.(buffer); },
    restore() {
      globalThis.AudioContext = oldAudioContext;
      globalThis.setTimeout = oldSetTimeout;
      globalThis.clearTimeout = oldClearTimeout;
    },
  };
}

test("PCM starts with a short prebuffer, keeps chunks contiguous, and reports playback drain", () => {
  const audio = installAudioContext();
  try {
    const events = [];
    const playback = new BrowserAudioPlayback({
      onStart: () => events.push("start"),
      onDrain: () => events.push("drain"),
      onError: (error) => events.push(`error:${error.message}`),
    });
    playback.playPcm16("AAAAAA==", 16_000);
    playback.playPcm16("AAAAAA==", 16_000);
    assert.equal(audio.scheduled.length, 2);
    assert.equal(audio.scheduled[0], 10.08);
    assert.ok(audio.scheduled[1] >= audio.scheduled[0] + 2 / 16_000 - 1e-9);
    assert.deepEqual(events, []);

    audio.timers[0]();
    assert.deepEqual(events, ["start"]);
    playback.finish();
    audio.sources[0].end();
    assert.deepEqual(events, ["start"]);
    audio.sources[1].end();
    assert.deepEqual(events, ["start", "drain"]);
  } finally {
    audio.restore();
  }
});

test("stopping playback invalidates an encoded response that is still decoding", async () => {
  const audio = installAudioContext();
  try {
    const events = [];
    const playback = new BrowserAudioPlayback({
      onStart: () => events.push("start"),
      onDrain: () => events.push("drain"),
      onError: (error) => events.push(`error:${error.message}`),
    });
    playback.enqueueEncoded("AQID", false);
    playback.finish();
    playback.stop();
    audio.resolveDecode({ duration: 1, getChannelData: () => new Float32Array(1) });
    await Promise.resolve();
    await Promise.resolve();
    assert.deepEqual(audio.scheduled, []);
    assert.deepEqual(events, []);
  } finally {
    audio.restore();
  }
});

test("encoded audio over the fixed memory cap fails before decoding", () => {
  const audio = installAudioContext();
  try {
    const errors = [];
    const playback = new BrowserAudioPlayback({ onError: (error) => errors.push(error.message) });
    const overLimitBase64 = "A".repeat(Math.ceil((16 * 1024 * 1024 + 1) * 4 / 3));
    playback.enqueueEncoded(overLimitBase64, false);
    assert.deepEqual(errors, ["Encoded audio exceeded the playback limit."]);
    assert.deepEqual(audio.scheduled, []);
  } finally {
    audio.restore();
  }
});
