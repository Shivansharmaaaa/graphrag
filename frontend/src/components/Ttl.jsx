import { useEffect, useState } from "react";

// Shared 1-second clock so every TTL on screen ticks in step.
export function useNow(ms = 1000) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), ms);
    return () => clearInterval(t);
  }, [ms]);
  return now;
}

export function fmtTtl(s) {
  if (s === null || s === undefined) return "—";
  if (s <= 0) return "expired";
  const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  if (d) return `${d}d ${h}h`;
  if (h) return `${h}h ${m}m`;
  if (m) return `${m}m ${sec}s`;
  return `${sec}s`;
}

/** Live countdown from a TTL captured at `fetchedAt` (ms). */
export default function Ttl({ ttl, fetchedAt, total }) {
  const now = useNow();
  if (ttl === null || ttl === undefined) return <span className="muted">—</span>;
  const left = Math.max(0, Math.round(ttl - (now - fetchedAt) / 1000));
  const pct = total ? Math.max(0, Math.min(100, (left / total) * 100)) : null;
  const cls = left <= 0 ? "ttl dead" : left < 300 ? "ttl hot" : "ttl";
  return (
    <span className={cls}>
      {fmtTtl(left)}
      {pct !== null && (
        <span className="ttl-bar">
          <span style={{ width: `${pct}%` }} />
        </span>
      )}
    </span>
  );
}
