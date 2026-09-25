import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, qs } from "../api.js";
import { hasRole, useUser } from "../App.jsx";
import ErrorBox from "../components/ErrorBox.jsx";
import Json from "../components/Json.jsx";
import TlpBadge from "../components/TlpBadge.jsx";

const CORE = ["_id", "title", "source", "date", "tlp", "confidence", "body", "actors", "campaigns", "malware", "iocs", "variable_fields"];

function ReportView({ id, onDeleted }) {
  const user = useUser();
  const [doc, setDoc] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => {
    setDoc(null);
    setErr(null);
    api(`/reports/${id}`).then(setDoc).catch(setErr);
  }, [id]);
  if (err)
    return (
      <div className="card">
        <ErrorBox error={err} />
        {err.status === 403 && <div className="muted">The document exists but its body is withheld by TLP policy (FR11).</div>}
      </div>
    );
  if (!doc) return <div className="card muted">Loading…</div>;
  const variable = Object.fromEntries(doc.variable_fields.map((k) => [k, doc[k]]));
  const del = async () => {
    if (!window.confirm(`Delete ${id}? This removes the MongoDB document, its Qdrant chunks and the Report node.`)) return;
    await api(`/reports/${id}`, { method: "DELETE" });
    onDeleted();
  };
  return (
    <div className="card">
      <div className="row">
        <h2 style={{ margin: 0 }}>{doc.title}</h2>
        <TlpBadge tlp={doc.tlp} />
      </div>
      <div className="muted small">
        {doc._id} · {doc.source} · {doc.date} · confidence {String(doc.confidence)}
      </div>
      <p className="body-text">{doc.body}</p>
      <div className="grid2">
        <div>
          <h4>Core envelope</h4>
          <div className="small">
            actors: {(doc.actors || []).join(", ") || "—"}
            <br />
            campaigns: {(doc.campaigns || []).join(", ") || "—"}
            <br />
            malware: {(doc.malware || []).join(", ") || "—"}
          </div>
          <h4>IOCs</h4>
          {doc.iocs?.length ? (
            <ul className="list mono small">
              {doc.iocs.map((v) => (
                <li key={v}>{v}</li>
              ))}
            </ul>
          ) : (
            <div className="muted small">No iocs[] array in this document.</div>
          )}
        </div>
        <div>
          <h4>Report-specific fields (schema-on-read)</h4>
          {doc.variable_fields.length ? <Json value={variable} /> : <div className="muted small">none</div>}
        </div>
      </div>
      <details>
        <summary>Raw document</summary>
        <Json value={Object.fromEntries(Object.entries(doc).filter(([k]) => k !== "variable_fields"))} />
      </details>
      {hasRole(user, "admin") && (
        <button className="danger" onClick={del}>
          Delete report (cascade)
        </button>
      )}
    </div>
  );
}

export default function Reports() {
  const { id } = useParams();
  const nav = useNavigate();
  const [f, setF] = useState({ actor: "", tlp: "", q: "" });
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const load = () => api(`/reports${qs(f)}`).then(setData).catch(setErr);
  useEffect(() => {
    load();
  }, []);
  return (
    <div className="page">
      <h1>Report browser</h1>
      <p className="lede">MongoDB is the system of record for reports. Documents share a small core envelope and diverge on nested, report-specific keys.</p>
      <div className="split">
        <div className="card">
          <form className="row" onSubmit={(e) => (e.preventDefault(), load())}>
            <input placeholder="text" value={f.q} onChange={(e) => setF({ ...f, q: e.target.value })} />
            <input placeholder="actor id (apt28)" value={f.actor} onChange={(e) => setF({ ...f, actor: e.target.value })} />
            <select value={f.tlp} onChange={(e) => setF({ ...f, tlp: e.target.value })}>
              <option value="">any TLP</option>
              {["WHITE", "GREEN", "AMBER", "RED"].map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
            <button>Filter</button>
          </form>
          <ErrorBox error={err} />
          {data && (
            <>
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Report</th>
                    <th>Date</th>
                    <th>TLP</th>
                    <th>Nested fields</th>
                  </tr>
                </thead>
                <tbody>
                  {data.reports.map((r) => (
                    <tr key={r._id} className={id === r._id ? "active" : ""}>
                      <td>
                        <Link to={`/reports/${r._id}`}>{r.title}</Link>
                        <div className="muted small">
                          {r._id} · {(r.actors || []).join(", ")}
                        </div>
                      </td>
                      <td className="small">{r.date}</td>
                      <td>
                        <TlpBadge tlp={r.tlp} />
                      </td>
                      <td className="small muted">{r.variable_fields.filter((k) => !CORE.includes(k)).join(", ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {data.hidden_by_tlp > 0 && <div className="muted small">{data.hidden_by_tlp} report(s) above your clearance are not listed.</div>}
            </>
          )}
        </div>
        <div>{id ? <ReportView id={id} onDeleted={() => (nav("/reports"), load())} /> : <div className="card muted">Select a report.</div>}</div>
      </div>
    </div>
  );
}
