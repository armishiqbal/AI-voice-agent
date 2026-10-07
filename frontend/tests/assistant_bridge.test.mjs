import test from "node:test";
import assert from "node:assert/strict";
import {
  ASSISTANT_BRIDGE_CHANNEL,
  ASSISTANT_BRIDGE_VERSION,
  ASSISTANT_MESSAGE_MAX_LENGTH,
  createFrameStatusMessage,
  createHelloMessage,
  createSubmitTextMessage,
  hasTrustedMessageOriginAndSource,
  parseFrameMessage,
  parseParentMessage,
} from "../../shared/assistantBridge.mjs";

const envelope = { channel: ASSISTANT_BRIDGE_CHANNEL, version: ASSISTANT_BRIDGE_VERSION };

test("parses bounded assistant text requests and trims whitespace", () => {
  assert.deepEqual(parseParentMessage({ ...envelope, type: "submit_text", text: "  Find a rental  " }),
    createSubmitTextMessage("Find a rental"));
});

test("parses the parent handshake without accepting extra payload", () => {
  assert.deepEqual(parseParentMessage({ ...envelope, type: "hello" }), createHelloMessage());
  assert.equal(parseParentMessage({ ...envelope, type: "hello", transcript: "private" }), null);
});

test("rejects empty, oversized, wrong-version, and non-text bridge requests", () => {
  assert.equal(parseParentMessage({ ...envelope, type: "submit_text", text: "  " }), null);
  assert.equal(parseParentMessage({ ...envelope, type: "submit_text", text: "x".repeat(ASSISTANT_MESSAGE_MAX_LENGTH + 1) }), null);
  assert.equal(parseParentMessage({ ...envelope, version: 2, type: "submit_text", text: "Buy a home" }), null);
  assert.equal(parseParentMessage({ ...envelope, type: "transcript", text: "private conversation" }), null);
});

test("accepts only known readiness and conversation phases", () => {
  assert.deepEqual(parseFrameMessage({ ...envelope, type: "ready", phase: "idle" }),
    createFrameStatusMessage("ready", "idle"));
  assert.deepEqual(parseFrameMessage({ ...envelope, type: "state", phase: "speaking" }),
    createFrameStatusMessage("state", "speaking"));
  assert.equal(parseFrameMessage({ ...envelope, type: "state", phase: "connected" }), null);
  assert.equal(parseFrameMessage({ ...envelope, type: "state", phase: "thinking", transcript: "private" }), null);
});

test("accepts bridge events only from the expected frame and allowed origin", () => {
  const parent = {};
  const frame = {};
  assert.equal(hasTrustedMessageOriginAndSource({ source: frame, origin: "http://127.0.0.1:8000" }, frame,
    ["http://127.0.0.1:8000"]), true);
  assert.equal(hasTrustedMessageOriginAndSource({ source: parent, origin: "http://127.0.0.1:8000" }, frame,
    ["http://127.0.0.1:8000"]), false);
  assert.equal(hasTrustedMessageOriginAndSource({ source: frame, origin: "https://attacker.example" }, frame,
    ["http://127.0.0.1:8000"]), false);
});
