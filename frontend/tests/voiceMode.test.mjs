import test from "node:test";
import assert from "node:assert/strict";

import { voiceModeForLanguage } from "../src/voiceMode.mjs";

test("English uses the Deepgram hybrid route", () => {
  assert.equal(voiceModeForLanguage("en"), "hybrid");
});

test("UrduLish uses Deepgram Urdu hybrid while other supported languages use OpenAI transcription", () => {
  for (const language of ["ur-Latn", "ur-Arab"]) {
    assert.equal(voiceModeForLanguage(language), "hybrid");
  }
  for (const language of ["hi", "ar", "pa", "bn"]) {
    assert.equal(voiceModeForLanguage(language), "openai");
  }
});
