function record(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value) ? value : null;
}

function finiteNumber(value) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function integer(value) {
  const number = finiteNumber(value);
  return number !== null && Number.isInteger(number) && number >= 0 ? number : null;
}

export function parseAdminMetrics(value) {
  const root = record(value);
  const traces = record(root?.traces);
  const providerInput = record(root?.providers);
  const reasoningInput = record(root?.structured_reasoning);
  const sessionInput = record(root?.voice_sessions);
  const countersInput = record(traces?.counters);
  const measurementsInput = record(traces?.measurements);
  const events = integer(traces?.events);
  if (!traces || !providerInput || !sessionInput || !countersInput || !measurementsInput || events === null) {
    return null;
  }

  const counters = Object.fromEntries(
    Object.entries(countersInput).flatMap(([name, count]) => {
      const parsed = integer(count);
      return parsed === null ? [] : [[name, parsed]];
    }),
  );
  const measurements = Object.fromEntries(
    Object.entries(measurementsInput).flatMap(([name, measurement]) => {
      const item = record(measurement);
      const count = integer(item?.count);
      const p50 = finiteNumber(item?.p50);
      const p95 = finiteNumber(item?.p95);
      const p99 = finiteNumber(item?.p99);
      const mean = finiteNumber(item?.mean);
      return count === null || p50 === null || p95 === null || p99 === null || mean === null
        ? []
        : [[name, { count, p50, p95, p99, mean }]];
    }),
  );
  const providers = Object.fromEntries(
    Object.entries(providerInput).flatMap(([name, ready]) =>
      typeof ready === "boolean" ? [[name, ready]] : [],
    ),
  );
  const reasoningStatus = typeof reasoningInput?.status === "string" ? reasoningInput.status : null;
  const reasoningFallback = typeof reasoningInput?.fallback === "string" ? reasoningInput.fallback : null;
  const reasoningFailureCategory = typeof reasoningInput?.last_failure_category === "string"
    ? reasoningInput.last_failure_category
    : null;
  const dueFollowUps = Array.isArray(root?.follow_ups_due)
    ? root.follow_ups_due.flatMap((value) => {
      const item = record(value);
      return item
        && typeof item.lead_id === "string"
        && typeof item.intent === "string"
        && (item.city === null || typeof item.city === "string")
        && (item.area === null || typeof item.area === "string")
        && (item.budget_pkr === null || (typeof item.budget_pkr === "number" && Number.isInteger(item.budget_pkr)))
        && typeof item.follow_up_at === "string"
        && Number.isFinite(Date.parse(item.follow_up_at))
        ? [{
          lead_id: item.lead_id,
          intent: item.intent,
          city: item.city,
          area: item.area,
          budget_pkr: item.budget_pkr,
          follow_up_at: item.follow_up_at,
        }]
        : [];
    })
    : [];
  const active = integer(sessionInput.active);
  const maximum = integer(sessionInput.maximum);
  const available = integer(sessionInput.available);
  const perClientMaximum = integer(sessionInput.per_client_maximum);
  const traceP95 = finiteNumber(traces.p95_ms);
  const traceMean = finiteNumber(traces.mean_ms);
  if (
    active === null || maximum === null || available === null || perClientMaximum === null ||
    traceP95 === null || traceMean === null
  ) {
    return null;
  }

  return {
    traces: { events, counters, measurements, p95_ms: traceP95, mean_ms: traceMean },
    providers,
    reasoning: reasoningStatus
      ? { status: reasoningStatus, fallback: reasoningFallback, failure_category: reasoningFailureCategory }
      : null,
    follow_ups_due: dueFollowUps,
    voice_sessions: { active, maximum, available, per_client_maximum: perClientMaximum },
  };
}

export function formatMetricName(value) {
  const acronyms = { api: "API", deepgram: "Deepgram", elevenlabs: "ElevenLabs", openai: "OpenAI", rag: "RAG", stt: "STT", tts: "TTS", vad: "VAD" };
  return value
    .replace(/[._]/g, " ")
    .replaceAll(":", " · ")
    .split(/\s+/)
    .map((word) => acronyms[word.toLowerCase()] ?? word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export function providerPresentation(name, configured) {
  const isVoiceRoute = name.endsWith("_voice_ready") || name === "live_voice_pipeline_ready";
  if (isVoiceRoute) {
    return configured
      ? { label: "Configured · verify on call", className: "configured" }
      : { label: "Route unavailable", className: "unavailable" };
  }
  return configured
    ? { label: "Credentials detected", className: "configured" }
    : { label: "Not configured", className: "unavailable" };
}
