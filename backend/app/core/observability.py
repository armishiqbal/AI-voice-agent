from __future__ import annotations

import time
from collections import Counter, deque
from dataclasses import asdict, dataclass
from math import ceil
from uuid import uuid4


@dataclass(frozen=True)
class TraceEvent:
    trace_id: str
    conversation_id: str
    node: str
    duration_ms: float
    outcome: str


class TraceStore:
    """Bounded in-process trace sink; replace with OTEL exporter in deployment."""

    def __init__(self, limit: int = 1000) -> None:
        self.events: deque[TraceEvent] = deque(maxlen=limit)
        self.counts: Counter[str] = Counter()
        self.measurements: dict[str, deque[float]] = {}

    def record(self, conversation_id: str, node: str, started: float, outcome: str = "ok") -> str:
        trace_id = str(uuid4())
        self.events.append(
            TraceEvent(
                trace_id,
                conversation_id,
                node,
                round((time.perf_counter() - started) * 1000, 2),
                outcome,
            )
        )
        self.counts[f"{node}:{outcome}"] += 1
        return trace_id

    def increment(self, name: str, amount: int = 1) -> None:
        self.counts[name] += amount

    def observe(self, name: str, value: float | None, limit: int = 1000) -> None:
        if value is None:
            return
        values = self.measurements.setdefault(name, deque(maxlen=limit))
        values.append(value)

    def snapshot(self) -> dict[str, object]:
        def percentile(values: list[float], fraction: float) -> float:
            if not values:
                return 0
            ordered = sorted(values)
            index = min(len(ordered) - 1, max(0, ceil(len(ordered) * fraction) - 1))
            return ordered[index]

        durations = [event.duration_ms for event in self.events]
        measurements = {
            name: {
                "count": len(values),
                "p50": percentile(list(values), 0.50),
                "p95": percentile(list(values), 0.95),
            }
            for name, values in self.measurements.items()
        }
        return {
            "events": len(self.events),
            "counters": dict(self.counts),
            "measurements": measurements,
            "p95_ms": percentile(durations, 0.95),
            "recent": [asdict(item) for item in list(self.events)[-20:]],
        }
