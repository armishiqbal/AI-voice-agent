import test from "node:test";
import assert from "node:assert/strict";
import { formatMetricName, parseAdminMetrics, providerPresentation } from "../src/analytics.mjs";

const validMetrics = {
  traces: {
    events: 3,
    counters: { "agent:ok": 2, "tts:error": 1, ignored: -1 },
    measurements: {
      "voice.first_audio_latency_ms": { count: 2, p50: 180, p95: 220, p99: 220, mean: 200 },
      empty_sample: { count: 0, p50: 0, p95: 0, p99: 0, mean: 0 },
      bad_sample: { count: 1, p50: "unknown", p95: 1, p99: 1, mean: 1 },
    },
    p95_ms: 20,
    mean_ms: 15,
  },
  providers: { deepgram: true, openai: false, invalid: "ready" },
  structured_reasoning: { configured: true, status: "cooldown", fallback: "deterministic", last_failure_category: "rate_limited" },
  follow_ups_due: [{
    lead_id: "lead-1", intent: "sell", city: "Karachi", area: "DHA Phase 6",
    budget_pkr: null, follow_up_at: "2026-09-29T08:30:00+00:00",
  }],
  voice_sessions: { active: 1, maximum: 20, available: 19, per_client_maximum: 2 },
};

test("parses only finite live metrics and safely omits malformed fields", () => {
  assert.deepEqual(parseAdminMetrics(validMetrics), {
    traces: {
      events: 3,
      counters: { "agent:ok": 2, "tts:error": 1 },
      measurements: {
        "voice.first_audio_latency_ms": { count: 2, p50: 180, p95: 220, p99: 220, mean: 200 },
        empty_sample: { count: 0, p50: 0, p95: 0, p99: 0, mean: 0 },
      },
      p95_ms: 20,
      mean_ms: 15,
    },
    providers: { deepgram: true, openai: false },
    reasoning: { status: "cooldown", fallback: "deterministic", failure_category: "rate_limited" },
    follow_ups_due: [{
      lead_id: "lead-1", intent: "sell", city: "Karachi", area: "DHA Phase 6",
      budget_pkr: null, follow_up_at: "2026-09-29T08:30:00+00:00",
    }],
    voice_sessions: { active: 1, maximum: 20, available: 19, per_client_maximum: 2 },
  });
});

test("rejects an incomplete metrics response instead of treating it as zero activity", () => {
  assert.equal(parseAdminMetrics({ traces: {}, providers: {}, voice_sessions: {} }), null);
  assert.equal(parseAdminMetrics(null), null);
});

test("formats internal counter and latency names for a readable dashboard", () => {
  assert.equal(formatMetricName("voice.first_audio_latency_ms"), "Voice First Audio Latency Ms");
  assert.equal(formatMetricName("agent:provider_error"), "Agent · Provider Error");
  assert.equal(formatMetricName("openai.tts_first_audio_ms"), "OpenAI TTS First Audio Ms");
});

test("provider analytics distinguish configured voice routes from verified calls", () => {
  assert.deepEqual(providerPresentation("hybrid_voice_ready", true), {
    label: "Configured · verify on call",
    className: "configured",
  });
  assert.deepEqual(providerPresentation("live_voice_pipeline_ready", false), {
    label: "Route unavailable",
    className: "unavailable",
  });
  assert.deepEqual(providerPresentation("deepgram", true), {
    label: "Credentials detected",
    className: "configured",
  });
});
