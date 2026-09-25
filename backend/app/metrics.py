"""Per-store latency samples (FR9) and SLO targets (NFR2)."""
from __future__ import annotations

import threading
import time
from collections import deque
from contextlib import contextmanager

SLO_MS = {
    "redis": {"metric": "p99", "target_ms": 5},
    "neo4j": {"metric": "p95", "target_ms": 500},
    "graphrag": {"metric": "p95", "target_ms": 15000},
}

_samples: dict[str, deque] = {}
_lock = threading.Lock()


def record(store: str, ms: float) -> None:
    with _lock:
        _samples.setdefault(store, deque(maxlen=2000)).append(ms)


@contextmanager
def timed(store: str, sink: dict | None = None):
    """Time a block; record globally and optionally add to a per-request dict."""
    t0 = time.perf_counter()
    try:
        yield
    finally:
        ms = (time.perf_counter() - t0) * 1000
        record(store, ms)
        if sink is not None:
            sink[store] = round(sink.get(store, 0.0) + ms, 2)


def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    v = sorted(values)
    k = max(0, min(len(v) - 1, int(round(p / 100 * (len(v) - 1)))))
    return round(v[k], 2)


def summary() -> dict:
    out = {}
    with _lock:
        items = {k: list(v) for k, v in _samples.items()}
    for store, vals in items.items():
        row = {
            "count": len(vals),
            "p50_ms": _pct(vals, 50),
            "p95_ms": _pct(vals, 95),
            "p99_ms": _pct(vals, 99),
        }
        if store in SLO_MS:
            slo = SLO_MS[store]
            row["slo"] = f"{slo['metric']} < {slo['target_ms']} ms"
            row["slo_met"] = row[f"{slo['metric']}_ms"] < slo["target_ms"] if vals else None
        out[store] = row
    return out
