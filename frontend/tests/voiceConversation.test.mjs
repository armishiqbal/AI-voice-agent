import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const source = await readFile(new URL("../src/voiceConversation.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText;
const voiceConversation = await import(
  `data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`
);

test("voice blocks only after the server confirms no provider is ready", () => {
  assert.equal(voiceConversation.resolveLiveVoiceAction(true), "connect");
  assert.equal(voiceConversation.resolveLiveVoiceAction(false), "blocked");
  assert.equal(voiceConversation.resolveLiveVoiceAction(null), "connect");
});

test("voice reconnects after transient network loss or backend restart, but stays bounded", () => {
  assert.equal(voiceConversation.shouldAutoReconnectVoice(1012, true, 0), true);
  assert.equal(voiceConversation.shouldAutoReconnectVoice(1006, true, 2), true);
  assert.equal(voiceConversation.shouldAutoReconnectVoice(1006, true, 3), false);
  assert.equal(voiceConversation.shouldAutoReconnectVoice(1008, true, 0), false);
  assert.equal(voiceConversation.shouldAutoReconnectVoice(1012, false, 0), false);
  assert.deepEqual([1, 2, 3].map(voiceConversation.voiceReconnectDelayMs), [500, 1_000, 2_000]);
});

test("an intentional stop closes normally and removes stale call callbacks", () => {
  const closed = [];
  const socket = {
    onopen: () => {}, onclose: () => {}, onerror: () => {}, onmessage: () => {},
    close: (...args) => closed.push(args),
  };
  voiceConversation.closeVoiceSession(socket);
  assert.deepEqual(closed, [[1000, "User ended voice chat"]]);
  assert.equal(socket.onopen, null);
  assert.equal(socket.onclose, null);
  assert.equal(socket.onerror, null);
  assert.equal(socket.onmessage, null);
  assert.doesNotThrow(() => voiceConversation.closeVoiceSession(null));
});

test("interruption rejects old audio and accepts only the next response generation", () => {
  const tracker = new voiceConversation.VoiceResponseTracker();
  assert.equal(tracker.accept({ type: "agent_response", response_id: 1 }), true);
  tracker.interrupt();
  assert.equal(tracker.accept({ type: "audio_chunk", response_id: 1 }), false);
  assert.equal(tracker.accept({ type: "state", response_id: 2 }), true);
  assert.equal(tracker.accept({ type: "audio_chunk", response_id: 1 }), false);
  assert.equal(tracker.accept({ type: "agent_response", response_id: 3 }), true);
  tracker.reset();
  assert.equal(tracker.accept({ type: "state", response_id: 1 }), true);
});

test("manual STT receives bounded leading audio and active turns, not indefinite silence", () => {
  const gate = new voiceConversation.VoiceInputGate(8);
  for (let i = 0; i < 20; i++) assert.deepEqual(gate.push(new Uint8Array([i, i, i, i])), []);
  const leading = gate.start();
  assert.equal(leading.reduce((sum, frame) => sum + frame.length, 0), 8);
  assert.equal(leading[1][0], 19);
  assert.equal(gate.push(new Uint8Array([1, 2])).length, 1);
  gate.end();
  assert.deepEqual(gate.push(new Uint8Array([0, 0])), []);
});
