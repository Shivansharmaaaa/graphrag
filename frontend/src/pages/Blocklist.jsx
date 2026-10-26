import { useEffect, useState } from "react";
import { api } from "../api.js";
import { hasRole, useUser } from "../App.jsx";
import ErrorBox from "../components/ErrorBox.jsx";
import GraphCanvas from "../components/GraphCanvas.jsx";
import Ttl from "../components/Ttl.jsx";

const TTL_PRESETS = [
  ["2 minutes (demo)", 120],
  ["1 hour", 3600],
  ["12 hours", 43200],
  ["1 day", 86400],
  ["7 days", 604800],
  ["30 days", 2592000],
];

export default function Blocklist() {
  const user = useUser();
  const canPublish = hasRole(user, "lead");
  const [data, setData] = useState(null);
  const [at, setAt] = useState(Date.now());
  const [err, setErr] = useState(null);
  const [form, setForm] = useState({ type: "ip", value: "", ttl: 86400, severity: "high", actor: "", campaign: "" });
  const [look, setLook] = useState({ type: "ip", value: "185.86.77.12" });
  const [lookRes, setLookRes] = useState(null);
  const [hist, setHist] = useState(null);
  const [refused, setRefused] = useState([]);

  const load = () => {
    api("/blocklist/blocked-requests").then(setRefused).catch(() => {});
    return api("/blocklist")
      .then((d) => {
        setData(d);
        setAt(Date.now());
        setErr(null);
      })
      .catch(setErr);
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  const publish = async (e) => {
    e.preventDefault();
    try {
      await api("/blocklist", { method: "POST", body: { ...form, actor: form.actor || null, campaign: form.campaign || null } });
      setForm({ ...form, value: "" });
      load();
    } catch (e2) {
      setErr(e2);
    }
  };
  const revoke = async (x) => {
    await api(`/blocklist/${x.type}/${encodeURIComponent(x.value)}`, { method: "DELETE" }).catch(setErr);
    load();
  };
  const lookup = async (e) => {
    e?.preventDefault();
    try {
      setLookRes({ ...(await api(`/blocklist/${look.type}/${encodeURIComponent(look.value)}`)), _at: Date.now() });
    } catch (e2) {
      setErr(e2);
    }
  };
  const history = (value) => api(`/graph/indicator/${encodeURIComponent(value)}`).then((h) => setHist({ value, ...h })).catch(setErr);

  return (
    <div className="page">
      <h1>IOC blocklist · enforcement plane</h1>
      <p className="lede">
        Redis keys <code>ioc:&#123;type&#125;:&#123;value&#125;</code> with per-key EXPIRE. When a TTL reaches zero the key leaves the hot set, while the graph and reports keep
        the historical fact (UC4). Enforcement consumers call <code>/api/enforce/check</code> with an API key and never see report bodies.
      </p>
      <ErrorBox error={err} />
      <div className="split wide-left">
        <div className="stack">
        <div className="card">
          <h3>Hot set {data && <span className="muted small">({data.live.length} live · refreshed every 5 s)</span>}</h3>
          <table className="tbl">
            <thead>
              <tr>
                <th>Type</th>
                <th>Value</th>
                <th>Severity</th>
                <th>Actor / campaign</th>
                <th>TTL remaining</th>
                <th>Published by</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data?.live.map((x) => (
                <tr key={x.key}>
                  <td>{x.type}</td>
                  <td className="mono">
                    <button className="link mono" onClick={() => history(x.value)}>
                      {x.value}
                    </button>
                  </td>
                  <td>
                    <span className={`sev sev-${x.severity}`}>{x.severity}</span>
                  </td>
                  <td className="small">
                    {x.actor || "—"} / {x.campaign || "—"}
                  </td>
                  <td>
                    <Ttl ttl={x.ttl_remaining} fetchedAt={at} total={x.ttl} />
                  </td>
                  <td className="small muted">{x.published_by}</td>
                  <td>{canPublish && <button className="link danger-text" onClick={() => revoke(x)}>revoke</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {data?.expired.length > 0 && (
            <>
              <h4>Recently expired (no longer asserted as actionable)</h4>
              <ul className="list small">
                {data.expired.map((x) => (
                  <li key={x.key}>
                    <span className="mono">{x.value}</span> — expired ·{" "}
                    <button className="link" onClick={() => history(x.value)}>
                      show historical graph presence
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
          <div className="card">
            <h3>Requests blocked by the API ({refused.length})</h3>
            <div className="muted small">
              Every API request from an IP that is live on this blocklist gets HTTP 403. Each refusal is logged in
              MongoDB (<span className="mono">blocked_requests</span>) and deleted automatically by a TTL index.
            </div>
            {refused.length === 0 ? (
              <div className="muted small">No blocked requests in the log.</div>
            ) : (
              <table className="tbl small">
                <thead>
                  <tr>
                    <th>When</th>
                    <th>Source IP</th>
                    <th>Request</th>
                    <th>Blocked by</th>
                    <th>Log expires</th>
                  </tr>
                </thead>
                <tbody>
                  {refused.slice(0, 20).map((r, i) => (
                    <tr key={i}>
                      <td>{new Date(r.ts).toLocaleTimeString()}</td>
                      <td className="mono">{r.ip}</td>
                      <td className="mono">
                        {r.method} {r.path}
                      </td>
                      <td>
                        <span className="mono">{r.ioc_key}</span> · {r.severity}
                      </td>
                      <td>{new Date(r.expires_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
        <div className="stack">
          <form className="card" onSubmit={lookup}>
            <h3>O(1) lookup</h3>
            <div className="row">
              <select value={look.type} onChange={(e) => setLook({ ...look, type: e.target.value })}>
                {["ip", "domain", "hash", "url"].map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </select>
              <input value={look.value} onChange={(e) => setLook({ ...look, value: e.target.value })} />
              <button>GET</button>
            </div>
            {lookRes && (
              <div className={lookRes.blocked ? "ok-box" : "warn"}>
                {lookRes.blocked ? (
                  <>
                    BLOCKED · severity {lookRes.severity} · <Ttl ttl={lookRes.ttl_remaining} fetchedAt={lookRes._at} />
                  </>
                ) : (
                  <>Not in the hot set (miss). The enforcement path does not fall back to MongoDB.</>
                )}{" "}
                <button type="button" className="link" onClick={() => history(lookRes.value)}>
                  history
                </button>
              </div>
            )}
          </form>
          {canPublish ? (
            <form className="card" onSubmit={publish}>
              <h3>Publish / refresh IOC</h3>
              <div className="row">
                <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
                  {["ip", "domain", "hash", "url"].map((t) => (
                    <option key={t}>{t}</option>
                  ))}
                </select>
                <input required placeholder="value" value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })} />
              </div>
              <div className="row">
                <select value={form.ttl} onChange={(e) => setForm({ ...form, ttl: +e.target.value })}>
                  {TTL_PRESETS.map(([l, v]) => (
                    <option key={v} value={v}>
                      {l}
                    </option>
                  ))}
                </select>
                <select value={form.severity} onChange={(e) => setForm({ ...form, severity: e.target.value })}>
                  {["low", "medium", "high", "critical"].map((t) => (
                    <option key={t}>{t}</option>
                  ))}
                </select>
              </div>
              <div className="row">
                <input placeholder="actor id (optional)" value={form.actor} onChange={(e) => setForm({ ...form, actor: e.target.value })} />
                <input placeholder="campaign id (optional)" value={form.campaign} onChange={(e) => setForm({ ...form, campaign: e.target.value })} />
              </div>
              <button className="primary">SET … EX {form.ttl}</button>
              <div className="muted small">Publishing never rewrites the historical graph (FR12).</div>
            </form>
          ) : (
            <div className="card muted small">Publishing and revoking require the CTI lead role.</div>
          )}
          {hist && (
            <div className="card">
              <h3>History of {hist.value}</h3>
              <div className="muted small">Graph presence (HAS_IOC / OBSERVED_AS) is independent of Redis TTL.</div>
              {hist.graph.nodes.length ? <GraphCanvas data={hist.graph} height={240} /> : <div className="muted">not in the graph</div>}
              <div className="small">
                Mentioned in: {hist.documents.map((d) => d._id).join(", ") || "no readable documents"}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
