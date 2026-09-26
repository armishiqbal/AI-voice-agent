import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const source = await readFile(new URL("../src/voiceProtocol.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText;
const protocol = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`);

const vadSource = await readFile(new URL("../src/voiceVad.ts", import.meta.url), "utf8");
const vadCompiled = ts.transpileModule(vadSource, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText;
const vadModule = await import(`data:text/javascript;base64,${Buffer.from(vadCompiled).toString("base64")}`);

test("parseServerEvent validates known voice events", () => {
  assert.deepEqual(protocol.parseServerEvent(JSON.stringify({
    type: "state",
    state: "listening",
    audio_input_available: true,
  })), {
    type: "state",
    state: "listening",
    audio_input_available: true,
  });

  const completedPlayback = protocol.parseServerEvent(JSON.stringify({
    type: "state",
    state: "listening",
  }));
  const interruptedPlayback = protocol.parseServerEvent(JSON.stringify({
    type: "state",
    state: "listening",
    interrupt_playback: true,
  }));
  assert.equal(protocol.shouldInterruptPlayback(completedPlayback), false);
  assert.equal(protocol.shouldInterruptPlayback(interruptedPlayback), true);

  assert.equal(protocol.parseServerEvent(JSON.stringify({
    type: "agent_response",
    decision: { kind: "answer", spoken_text: "Assalam-o-Alaikum", property_ids: ["PROP-001"] },
  })).decision.spoken_text, "Assalam-o-Alaikum");
});

test("parseServerEvent rejects malformed, unknown, and unsafe audio events", () => {
  assert.equal(protocol.parseServerEvent("not json"), null);
  assert.equal(protocol.parseServerEvent(JSON.stringify(["state"])), null);
  assert.equal(protocol.parseServerEvent(JSON.stringify({ type: "unknown" })), null);
  assert.equal(protocol.parseServerEvent(JSON.stringify({
    type: "audio_chunk",
    encoding: "pcm_s16le",
    sample_rate: 192_000,
    audio_base64: "AAAA",
  })), null);
  assert.equal(protocol.parseServerEvent(JSON.stringify({
    type: "audio_chunk",
    encoding: "pcm_s16le",
    sample_rate: 24_000,
    audio_base64: "not base64!",
  })), null);
  assert.equal(protocol.parseServerEvent(" ".repeat(protocol.MAX_SERVER_EVENT_CHARS + 1)), null);
});

test("parseServerEvent accepts bounded low-confidence transcripts for retry handling", () => {
  assert.deepEqual(protocol.parseServerEvent(JSON.stringify({
    type: "transcript_low_confidence",
    text: "Find me a home",
    confidence: 0.32,
  })), {
    type: "transcript_low_confidence",
    text: "Find me a home",
    confidence: 0.32,
  });
  assert.equal(protocol.parseServerEvent(JSON.stringify({
    type: "transcript_low_confidence",
    text: "Find me a home",
    confidence: 1.5,
  })), null);
});

test("parseServerEvent validates consent status and non-PII appointment outcomes", () => {
  assert.equal(protocol.parseServerEvent(JSON.stringify({
    type: "booking_contact_status",
    ready: true,
  })).ready, true);
  assert.deepEqual(protocol.parseServerEvent(JSON.stringify({
    type: "booking_slots",
    property_id: "PROP-001",
    slots: ["2026-09-23T10:00:00+05:00"],
  })).slots, ["2026-09-23T10:00:00+05:00"]);
  assert.equal(protocol.parseServerEvent(JSON.stringify({
    type: "booking_slots",
    property_id: "PROP-001",
    slots: ["a", "b", "c", "d"],
  })), null);
  assert.equal(protocol.parseServerEvent(JSON.stringify({
    type: "appointment_result",
    status: "pending_calendar",
    reference: "AES-0123456789",
    property_id: "PROP-001",
    starts_at: "2026-09-23T10:00:00+05:00",
  })).status, "pending_calendar");
  assert.equal(protocol.parseServerEvent(JSON.stringify({
    type: "appointment_result",
    status: "confirmed",
    reference: "AES-0123456789",
    property_id: "PROP-001",
    starts_at: "2026-09-23T10:00:00+05:00",
  })), null);
});

test("audioUplinkState stops capture before the browser send queue grows without bound", () => {
  assert.equal(protocol.audioUplinkState(1, 0), "ready");
  assert.equal(protocol.audioUplinkState(1, protocol.AUDIO_UPLINK_HIGH_WATER_BYTES), "backpressured");
  assert.equal(protocol.audioUplinkState(1, -1), "backpressured");
  assert.equal(protocol.audioUplinkState(3, 0), "closed");
});

test("adaptive voice activity detection starts on quiet speech and ends after silence", () => {
  const vad = new vadModule.VoiceActivityDetector();
  assert.equal(vad.process(0.001, 256), null);
  assert.equal(vad.process(0.006, 256), "speech_started");
  assert.equal(vad.process(0.01, 256), null);
  assert.equal(vad.process(0.001, 256), null);
  assert.equal(vad.process(0.001, 256), null);
  assert.equal(vad.process(0.001, 256), "speech_ended");
});

test("adaptive voice activity detection learns background noise and bounds long turns", () => {
  const vad = new vadModule.VoiceActivityDetector(650, 1_000);
  for (let index = 0; index < 12; index += 1) {
    assert.equal(vad.process(0.006, 100), null);
  }
  assert.equal(vad.process(0.01, 100), null);
  assert.equal(vad.process(0.01, 100), "speech_started");
  assert.equal(vad.process(0.03, 500), null);
  assert.equal(vad.process(0.03, 500), "speech_ended");
});

test("a short microphone click does not begin a voice turn", () => {
  const vad = new vadModule.VoiceActivityDetector();
  assert.equal(vad.process(0.001, 350), null);
  assert.equal(vad.process(0.1, 85), null);
  assert.equal(vad.process(0.001, 85), null);
  assert.equal(vad.process(0.01, 85), null);
  assert.equal(vad.process(0.01, 85), "speech_started");
});


test("appointment outcome actions are bounded", () => {
  const event = { type: "appointment_result", status: "pending_calendar", reference: "AES-123", property_id: "PROP-001", starts_at: "2026-09-27T10:00:00Z" };
  for (const action of ["cancellation", "reschedule"]) {
    assert.equal(protocol.parseServerEvent(JSON.stringify({ ...event, action })).action, action);
  }
  assert.equal(protocol.parseServerEvent(JSON.stringify({ ...event, action: "delete_all" })), null);
});
