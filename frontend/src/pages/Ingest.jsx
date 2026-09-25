import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { hasRole, useUser } from "../App.jsx";
import ErrorBox from "../components/ErrorBox.jsx";
import Json from "../components/Json.jsx";

const SAMPLE_TEXT = {
  title: "Fake recruiter lures deliver AppleJeus to crypto developers",
  body:
    "Lazarus Group operators posed as recruiters and sent trojanized coding challenges to cryptocurrency developers. " +
    "The archive fetched AppleJeus from jobs-portal-hr[.]com and beaconed to 203.0.113.9. Initial access used spearphishing (T1566). " +
    "Credential theft afterwards relied on Mimikatz, which is common to many clusters and should not be used alone for attribution.",
  extra: '{\n  "lure_themes": ["job offer", "coding test"],\n  "platforms": ["macOS", "Windows"]\n}',
};

function Steps({ job }) {
  return (
    <div className="steps">
      {Object.entries(job.steps).map(([k, v]) => (
        <span key={k} className={`step step-${v.status}`} title={v.error || JSON.stringify(v.result || {})}>
          {k}: {v.status}
          {v.ms !== undefined ? ` (${v.ms} ms)` : ""}
        </span>
      ))}
    </div>
  );
}

export default function Ingest() {
  const user = useUser();
  const can = hasRole(user, "lead");
  const [mode, setMode] = useState("text");
  const [t, setT] = useState({ title: "", body: "", source: "analyst", date: "", tlp: "AMBER", extra: "", publish_iocs: false, ttl: 86400 });
  const [stix, setStix] = useState("");
  const [stixOpts, setStixOpts] = useState({ default_tlp: "AMBER", publish_iocs: false, ttl: 86400 });
  const [result, setResult] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  const loadJobs = () => api("/ingest/jobs").then(setJobs).catch(setErr);
  useEffect(() => {
    loadJobs();
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      if (mode === "text") {
        let extra = null;
        if (t.extra.trim()) extra = JSON.parse(t.extra);
        setResult(await api("/ingest/report", { method: "POST", body: { ...t, date: t.date || null, extra } }));
      } else {
        setResult(await api("/ingest/stix", { method: "POST", body: { bundle: JSON.parse(stix), ...stixOpts } }));
      }
      loadJobs();
    } catch (e2) {
      setErr(e2);
    } finally {
      setBusy(false);
    }
  };

  const loadFile = (f) => f && f.text().then(setStix);
  const retry = (id) => api(`/ingest/jobs/${id}/retry`, { method: "POST" }).then(() => loadJobs()).catch(setErr);

  return (
    <div className="page">
      <h1>Ingest</h1>
      <p className="lede">
        One job fans out to Neo4j → MongoDB → Qdrant → Redis (optional) in a fixed order and records each step in the ingest log. Steps are idempotent, so a
        failed job is retried from the first incomplete step.
      </p>
      {!can && <div className="warn">Ingest requires the CTI lead or admin role. You can still view the job log.</div>}
      <div className="split">
        <form className="card" onSubmit={submit}>
          <div className="tabs">
            <button type="button" className={mode === "text" ? "on" : ""} onClick={() => setMode("text")}>
              Free-text report
            </button>
            <button type="button" className={mode === "stix" ? "on" : ""} onClick={() => setMode("stix")}>
              STIX 2.1 bundle
            </button>
          </div>
          {mode === "text" ? (
            <>
              <button type="button" className="link small" onClick={() => setT({ ...t, ...SAMPLE_TEXT })}>
                fill sample
              </button>
              <input required placeholder="Title" value={t.title} onChange={(e) => setT({ ...t, title: e.target.value })} />
              <textarea required rows={8} placeholder="Report body (entities and IOCs are extracted and linked automatically; defanged IOCs are refanged)" value={t.body} onChange={(e) => setT({ ...t, body: e.target.value })} />
              <div className="row">
                <input placeholder="source" value={t.source} onChange={(e) => setT({ ...t, source: e.target.value })} />
                <input type="date" value={t.date} onChange={(e) => setT({ ...t, date: e.target.value })} />
                <select value={t.tlp} onChange={(e) => setT({ ...t, tlp: e.target.value })}>
                  {["WHITE", "GREEN", "AMBER", "RED"].map((x) => (
                    <option key={x}>{x}</option>
                  ))}
                </select>
              </div>
              <textarea rows={4} className="mono" placeholder='Report-specific nested fields as JSON, e.g. {"ics_protocols": ["IEC-104"]}' value={t.extra} onChange={(e) => setT({ ...t, extra: e.target.value })} />
              <label className="inline">
                <input type="checkbox" checked={t.publish_iocs} onChange={(e) => setT({ ...t, publish_iocs: e.target.checked })} /> publish extracted IOCs to the blocklist with TTL
                <input type="number" value={t.ttl} min={60} onChange={(e) => setT({ ...t, ttl: +e.target.value })} style={{ width: 100 }} /> s
              </label>
            </>
          ) : (
            <>
              <div className="row">
                <input type="file" accept=".json" onChange={(e) => loadFile(e.target.files[0])} />
                <span className="muted small">or paste a bundle (see samples/stix_apt28_bundle.json)</span>
              </div>
              <textarea rows={14} className="mono" value={stix} onChange={(e) => setStix(e.target.value)} placeholder='{"type": "bundle", "objects": [...]}' />
              <div className="row">
                <label className="inline">
                  default TLP
                  <select value={stixOpts.default_tlp} onChange={(e) => setStixOpts({ ...stixOpts, default_tlp: e.target.value })}>
                    {["WHITE", "GREEN", "AMBER", "RED"].map((x) => (
                      <option key={x}>{x}</option>
                    ))}
                  </select>
                </label>
                <label className="inline">
                  <input type="checkbox" checked={stixOpts.publish_iocs} onChange={(e) => setStixOpts({ ...stixOpts, publish_iocs: e.target.checked })} /> publish
                  indicators (valid_until → TTL)
                </label>
              </div>
            </>
          )}
          <button className="primary" disabled={!can || busy}>
            {busy ? "Ingesting…" : "Run ingest job"}
          </button>
          <ErrorBox error={err} />
          {result && (
            <div className="card inner">
              <h4>
                Job {result._id} — {result.status}
              </h4>
              <Steps job={result} />
              {result.preview?.map((p) => (
                <div key={p._id} className="small">
                  <Link to={`/reports/${p._id}`}>{p._id}</Link> {p.title} · actors {p.actors.join(", ") || "—"} · malware {p.malware.join(", ") || "—"} · iocs{" "}
                  {p.iocs.join(", ") || "—"}
                </div>
              ))}
              {result.linked?.length > 0 && <div className="muted small">Linked: {result.linked.map((l) => `${l.name} (${l.label})`).join(", ")}</div>}
            </div>
          )}
        </form>
        <div className="card">
          <h3>Ingest log</h3>
          <table className="tbl small">
            <tbody>
              {jobs.map((j) => (
                <tr key={j._id}>
                  <td>
                    <b>{j._id}</b> · {j.kind} · {new Date(j.created_at * 1000).toLocaleString()} · {j.user}
                    <div>
                      {j.report_ids.map((r) => (
                        <Link key={r} to={`/reports/${r}`}>
                          {r}{" "}
                        </Link>
                      ))}
                    </div>
                    <Steps job={j} />
                    {j.error && <div className="danger-text">{j.error}</div>}
                  </td>
                  <td>{j.status !== "ok" && can && <button onClick={() => retry(j._id)}>retry</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {jobs.length === 0 && <div className="muted">No ingest jobs yet (the seed corpus is loaded directly).</div>}
          {result && (
            <details>
              <summary>Raw job</summary>
              <Json value={result} />
            </details>
          )}
        </div>
      </div>
    </div>
  );
}
