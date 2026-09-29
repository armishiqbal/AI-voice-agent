export type LatencyMeasurement = {
  count: number;
  p50: number;
  p95: number;
  p99: number;
  mean: number;
};

export type AdminMetrics = {
  traces: {
    events: number;
    counters: Record<string, number>;
    measurements: Record<string, LatencyMeasurement>;
    p95_ms: number;
    mean_ms: number;
  };
  providers: Record<string, boolean>;
  reasoning: { status: string; fallback: string | null; failure_category: string | null } | null;
  follow_ups_due: Array<{
    lead_id: string;
    intent: string;
    city: string | null;
    area: string | null;
    budget_pkr: number | null;
    follow_up_at: string;
  }>;
  voice_sessions: {
    active: number;
    maximum: number;
    available: number;
    per_client_maximum: number;
  };
};

export function parseAdminMetrics(value: unknown): AdminMetrics | null;
export function formatMetricName(value: string): string;
export function providerPresentation(name: string, configured: boolean): {
  label: string;
  className: "configured" | "unavailable";
};
