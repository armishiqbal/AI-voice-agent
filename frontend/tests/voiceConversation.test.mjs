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

test("voice starts only through a ready server provider", () => {
  assert.equal(voiceConversation.resolveLiveVoiceAction(true), "connect");
  assert.equal(voiceConversation.resolveLiveVoiceAction(false), "blocked");
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
