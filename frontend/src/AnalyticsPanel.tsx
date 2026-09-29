import React, { useRef, useState, type FormEvent } from "react";
import { formatMetricName, parseAdminMetrics, providerPresentation, type AdminMetrics } from "./analytics.mjs";
import { useNativeDialog } from "./useNativeDialog";

type AnalyticsPanelProps = {
  apiUrl: string;
  open: boolean;
  onClose: () => void;
};

function responseError(body: unknown, status: number): string {
  if (typeof body === "object" && body !== null && "detail" in body && typeof body.detail === "string") {
    return body.detail;
  }
  if (status === 401) return "Admin API key was rejected. Check the key and retry.";
  return `Could not load service metrics (HTTP ${status}). Check the API and retry.`;
}

function latency(value: number): string {
  return `${Math.round(value).toLocaleString()} ms`;
}

function followUpTime(value: string): string {
  return new Intl.DateTimeFormat("en-PK", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Karachi",
  }).format(new Date(value));
}

export function AnalyticsPanel({ apiUrl, open, onClose }: AnalyticsPanelProps) {
  const dialog = useNativeDialog(open);
  const [adminKey, setAdminKey] = useState("");
  const [metrics, setMetrics] = useState<AdminMetrics | null>(null);
  const [loading, setLoading] = useState(false);
  const [completingLeadId, setCompletingLeadId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const activeRequest = useRef<AbortController | null>(null);

  async function loadMetrics(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    setLoading(true);
    setError("");
    try {
      const key = adminKey.trim();
      const response = await fetch(`${apiUrl}/v1/admin/metrics`, {
        headers: key ? { "X-Admin-API-Key": key } : undefined,
        signal: controller.signal,
      });
      const body: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        setError(responseError(body, response.status));
        return;
      }
      const parsed = parseAdminMetrics(body);
      if (!parsed) {
        setError("The metrics endpoint returned an unexpected response. No dashboard data was displayed.");
        return;
      }
      setMetrics(parsed);
    } catch (cause: unknown) {
      if (cause instanceof Error && cause.name === "AbortError") return;
      setError("Could not reach the metrics service. Check the connection and retry.");
    } finally {
      if (activeRequest.current === controller) {
        activeRequest.current = null;
        setLoading(false);
      }
    }
  }

  function close() {
    activeRequest.current?.abort();
    activeRequest.current = null;
    setAdminKey("");
    setMetrics(null);
    setError("");
    setLoading(false);
    setCompletingLeadId(null);
    onClose();
  }

  async function completeFollowUp(leadId: string) {
    setCompletingLeadId(leadId);
    setError("");
    try {
      const key = adminKey.trim();
      const response = await fetch(`${apiUrl}/v1/admin/follow-ups/${encodeURIComponent(leadId)}/complete`, {
        method: "POST",
        headers: key ? { "X-Admin-API-Key": key } : undefined,
      });
      const body: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        setError(responseError(body, response.status));
        return;
      }
      await loadMetrics();
    } catch {
      setError("Could not update the follow-up reminder. Check the API and retry.");
    } finally {
      setCompletingLeadId(null);
    }
  }

  const measurementEntries = Object.entries(metrics?.traces.measurements ?? {}).sort(([left], [right]) => left.localeCompare(right));
  const counterEntries = Object.entries(metrics?.traces.counters ?? {}).sort(([left], [right]) => left.localeCompare(right));
  const providerEntries = Object.entries(metrics?.providers ?? {}).sort(([left], [right]) => left.localeCompare(right));
  const reasoningStatus = metrics?.reasoning?.status;
  const reasoningFailure = metrics?.reasoning?.failure_category;
  const reasoningLabel = reasoningFailure === "rate_limited"
    ? "Rate limited · deterministic fallback active"
    : reasoningFailure === "authentication_failed"
      ? "Credentials rejected · deterministic fallback active"
      : reasoningFailure === "timeout"
        ? "Timed out · deterministic fallback active"
        : reasoningStatus === "provider_error"
          ? "Provider error · deterministic fallback active"
          : reasoningStatus === "cooldown"
            ? "Temporarily unavailable"
            : reasoningStatus === "configured_unverified"
              ? "Configured · not health-checked"
              : reasoningStatus === "unconfigured"
                ? "Not configured"
                : "Status unavailable";

  return (
    <dialog
      ref={dialog}
      className="orbit-native-modal analytics-dialog"
      aria-labelledby="analytics-title"
      onCancel={(event) => { event.preventDefault(); close(); }}
      onClick={(event) => { if (event.target === event.currentTarget) close(); }}
    >
      <section className="orbit-modal-window analytics-window">
        <header className="modal-top">
          <div>
            <h2 id="analytics-title">Live service analytics</h2>
            <p className="analytics-subtitle">Live operational metrics from this API instance. No sample data.</p>
          </div>
          <button type="button" className="modal-x-btn" onClick={close} aria-label="Close analytics">✕</button>
        </header>

        {!metrics && (
          <form className="analytics-access" onSubmit={(event) => void loadMetrics(event)}>
            <label htmlFor="analytics-admin-key">Admin API key <small>(required outside development)</small></label>
            <input
              id="analytics-admin-key"
              type="password"
              autoComplete="off"
              value={adminKey}
              onChange={(event) => setAdminKey(event.target.value)}
              placeholder="Used for this request only"
            />
            <button type="submit" disabled={loading}>{loading ? "Loading live metrics…" : "Load live metrics"}</button>
          </form>
        )}

        {error && <p className="analytics-error" role="alert">{error}</p>}

        {metrics && (
          <div className="analytics-content" aria-live="polite">
            <div className="analytics-toolbar">
              <span>Trace history is bounded process memory; provider and session status are live API responses.</span>
              <button type="button" onClick={() => void loadMetrics()} disabled={loading}>
                {loading ? "Refreshing…" : "Refresh"}
              </button>
            </div>

            <section className="analytics-section" aria-labelledby="analytics-summary-title">
              <h3 id="analytics-summary-title">Runtime summary</h3>
              <div className="analytics-summary-grid">
                <article><span>Recorded trace events</span><strong>{metrics.traces.events.toLocaleString()}</strong></article>
                <article><span>Active voice sessions</span><strong>{metrics.voice_sessions.active} / {metrics.voice_sessions.maximum}</strong></article>
                <article><span>Available session capacity</span><strong>{metrics.voice_sessions.available}</strong></article>
                <article><span>Trace p95 <small>(all retained events)</small></span><strong>{metrics.traces.events ? latency(metrics.traces.p95_ms) : "No samples yet"}</strong></article>
              </div>
            </section>

            <section className="analytics-section" aria-labelledby="analytics-provider-title">
              <h3 id="analytics-provider-title">Provider readiness</h3>
              {providerEntries.length === 0 ? <p>No provider readiness fields were returned.</p> : (
                <ul className="analytics-provider-list">
                  {providerEntries.map(([name, ready]) => {
                    const presentation = providerPresentation(name, ready);
                    return (
                      <li key={name} className={presentation.className}>
                        <span className="analytics-provider-dot" />
                        <span>{formatMetricName(name)}</span>
                        <strong>{presentation.label}</strong>
                      </li>
                    );
                  })}
                </ul>
              )}
              <p className="analytics-footnote">“Credentials detected” confirms configuration only. Route availability does not prove usable provider credits or a completed call.</p>
              <div className={`analytics-reasoning ${reasoningStatus === "cooldown" || reasoningStatus === "provider_error" || reasoningStatus === "unconfigured" ? "attention" : ""}`} role="status">
                <span>Structured reasoning</span>
                <strong>{reasoningLabel}</strong>
                {metrics?.reasoning?.fallback && <small>Fallback: {formatMetricName(metrics.reasoning.fallback)}</small>}
              </div>
            </section>

            <section className="analytics-section" aria-labelledby="analytics-follow-up-title">
              <h3 id="analytics-follow-up-title">Due follow-up reminders</h3>
              {metrics.follow_ups_due.length === 0 ? (
                <p>No follow-ups are due.</p>
              ) : (
                <ul className="analytics-follow-up-list">
                  {metrics.follow_ups_due.map((item) => (
                    <li key={item.lead_id}>
                      <div>
                        <strong>{item.intent} · {item.city ?? "City not recorded"}{item.area ? ` · ${item.area}` : ""}</strong>
                        <span>Due {followUpTime(item.follow_up_at)} · Lead {item.lead_id.slice(0, 8)}</span>
                      </div>
                      <button
                        type="button"
                        onClick={() => void completeFollowUp(item.lead_id)}
                        disabled={loading || completingLeadId !== null}
                        aria-label={`Mark follow-up for lead ${item.lead_id.slice(0, 8)} complete`}
                      >
                        {completingLeadId === item.lead_id ? "Saving…" : "Mark complete"}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="analytics-section" aria-labelledby="analytics-latency-title">
              <h3 id="analytics-latency-title">Measured latency</h3>
              {measurementEntries.length === 0 ? <p>No latency samples have been recorded in this process yet.</p> : (
                <div className="analytics-table-wrap">
                  <table className="analytics-table">
                    <thead><tr><th>Metric</th><th>Samples</th><th>p50</th><th>p95</th><th>p99</th></tr></thead>
                    <tbody>
                      {measurementEntries.map(([name, sample]) => (
                        <tr key={name}>
                          <th scope="row">{formatMetricName(name)}</th>
                          <td>{sample.count.toLocaleString()}</td>
                          <td>{sample.count ? latency(sample.p50) : "—"}</td>
                          <td>{sample.count ? latency(sample.p95) : "—"}</td>
                          <td>{sample.count ? latency(sample.p99) : "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            <section className="analytics-section" aria-labelledby="analytics-counter-title">
              <h3 id="analytics-counter-title">Runtime counters</h3>
              {counterEntries.length === 0 ? <p>No events have been recorded in this process yet.</p> : (
                <ul className="analytics-counter-list">
                  {counterEntries.map(([name, count]) => <li key={name}><span>{formatMetricName(name)}</span><strong>{count.toLocaleString()}</strong></li>)}
                </ul>
              )}
            </section>
          </div>
        )}
      </section>
    </dialog>
  );
}
