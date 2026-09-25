import { useEffect, useState } from "react";
import { api } from "../api.js";
import { hasRole, useUser } from "../App.jsx";
import ErrorBox from "../components/ErrorBox.jsx";
import Json from "../components/Json.jsx";

export default function Ops() {
  const user = useUser();
  const [h, setH] = useState(null);
  const [meta, setMeta] = useState(null);
  const [integ, setInteg] = useState(null);
  const [msg, setMsg] = useState(null);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = () => {
    api("/health").then(setH).catch(setErr);
    api("/meta").then(setMeta).catch(setErr);
  };
  useEffect(() => {
    load();
    const t = setInterval(load, 8000);
    return () => clearInterval(t);
  }, []);

  const admin = async (path, label) => {
    if (!window.confirm(`${label}?`)) return;
    setBusy(true);
    try {
      setMsg(await api(path, { method: "POST" }));
      load();
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page">
      <h1>Operations</h1>
      <p className="lede">Store liveness, per-store latency against the NFR2 SLOs, cross-model integrity (Section 8.5) and operator actions.</p>
      <ErrorBox error={err} />
      {h && (
        <div className="grid-cards">
          {Object.entries(h.stores).map(([k, v]) => (
            <div key={k} className={`card stat ${v.ok ? "" : "down"}`}>
              <div className="stat-title">{k}</div>
              <div className={v.ok ? "ok-text" : "danger-text"}>{v.ok ? "UP" : "DOWN"}</div>
              <div className="muted small">{v.detail}</div>
              {v.latency_ms !== null && <div className="small mono">ping {v.latency_ms} ms</div>}
            </div>
          ))}
        </div>
      )}
      {h && (
        <div className="row">
          <span className={h.read_path_ok ? "ok-text" : "danger-text"}>Read path {h.read_path_ok ? "healthy" : "degraded"}</span>
          <span className={h.enforcement_path_ok ? "ok-text" : "danger-text"}>
            Enforcement path {h.enforcement_path_ok ? "healthy" : "FAILING CLOSED"}
          </span>
          {!h.startup.ok && <span className="danger-text">startup: {h.startup.detail}</span>}
        </div>
      )}
      <div className="split">
        <div className="card">
          <h3>Latency (process lifetime)</h3>
          <table className="tbl">
            <thead>
              <tr>
                <th>Channel</th>
                <th>n</th>
                <th>p50</th>
                <th>p95</th>
                <th>p99</th>
                <th>SLO</th>
              </tr>
            </thead>
            <tbody>
              {h &&
                Object.entries(h.latency).map(([k, v]) => (
                  <tr key={k}>
                    <td>{k}</td>
                    <td>{v.count}</td>
                    <td className="mono">{v.p50_ms}</td>
                    <td className="mono">{v.p95_ms}</td>
                    <td className="mono">{v.p99_ms}</td>
                    <td>{v.slo ? <span className={v.slo_met ? "ok-text" : "danger-text"}>{v.slo}</span> : "—"}</td>
                  </tr>
                ))}
            </tbody>
          </table>
          {meta && (
            <>
              <h3>Graph inventory</h3>
              <div className="small">
                {Object.entries(meta.graph.labels).map(([k, v]) => (
                  <span key={k} className="pill">
                    {k} {v}
                  </span>
                ))}
              </div>
              <div className="small" style={{ marginTop: 6 }}>
                {Object.entries(meta.graph.relationships).map(([k, v]) => (
                  <span key={k} className="pill">
                    {k} {v}
                  </span>
                ))}
              </div>
              <div className="muted small">
                Embeddings: {meta.embedder.backend} · dim {meta.embedder.dim} · LLM {meta.llm_model}
              </div>
            </>
          )}
        </div>
        <div className="card">
          <h3>Cross-model integrity</h3>
          <button onClick={() => api("/admin/integrity").then(setInteg).catch(setErr)}>Run check</button>
          {integ && (
            <ul className="list small">
              {integ.rules.map((r) => (
                <li key={r.rule}>
                  <span className={r.ok ? "ok-text" : "danger-text"}>{r.ok ? "✓" : "✗"}</span> {r.rule}
                  {!r.ok && <span className="muted"> — {r.violations.slice(0, 6).join(", ")}</span>}
                </li>
              ))}
            </ul>
          )}
          {hasRole(user, "admin") && (
            <>
              <h3>Operator actions</h3>
              <div className="row">
                <button disabled={busy} onClick={() => admin("/admin/seed", "Reload the initial corpus into all four stores (wipes ingested data)")}>
                  Re-seed corpus
                </button>
                <button disabled={busy} onClick={() => admin("/admin/reindex", "Refit embeddings and rebuild the Qdrant collection")}>
                  Rebuild vector index
                </button>
              </div>
              {msg && <Json value={msg} />}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
