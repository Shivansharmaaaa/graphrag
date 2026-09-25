import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api.js";
import ErrorBox from "../components/ErrorBox.jsx";
import TlpBadge from "../components/TlpBadge.jsx";

const ok = (b) => <span className={b ? "ok-text" : "danger-text"}>{b ? "✓" : "✗"}</span>;

export default function Audit() {
  const { id } = useParams();
  const [list, setList] = useState([]);
  const [doc, setDoc] = useState(null);
  const [rep, setRep] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    api("/audit").then(setList).catch(setErr);
  }, []);
  useEffect(() => {
    setDoc(null);
    setRep(null);
    if (id) api(`/audit/${id}`).then(setDoc).catch(setErr);
  }, [id]);

  const replay = () => api(`/audit/${id}/replay`, { method: "POST" }).then(setRep).catch(setErr);

  return (
    <div className="page">
      <h1>Audit log & replay</h1>
      <p className="lede">Every GraphRAG answer persists the hops, chunks, documents and IOC states it used (FR10). Replay re-checks each artefact against the live stores.</p>
      <ErrorBox error={err} />
      <div className="split">
        <div className="card">
          <table className="tbl small">
            <thead>
              <tr>
                <th>When</th>
                <th>Question</th>
                <th>Mode</th>
                <th>Coverage</th>
                <th>ms</th>
              </tr>
            </thead>
            <tbody>
              {list.map((a) => (
                <tr key={a._id} className={a._id === id ? "active" : ""}>
                  <td>{new Date(a.ts * 1000).toLocaleString()}</td>
                  <td>
                    <Link to={`/audit/${a._id}`}>{a.question}</Link>
                    <div className="muted">
                      {a.user} {a.refused && "· refused"}
                    </div>
                  </td>
                  <td>{a.mode}</td>
                  <td>{Math.round((a.citation_coverage || 0) * 100)}%</td>
                  <td>{a.latency_ms?.total}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {list.length === 0 && <div className="muted">No questions asked yet.</div>}
        </div>
        <div className="card">
          {!doc && <div className="muted">Select an entry.</div>}
          {doc && (
            <>
              <h3>{doc.question}</h3>
              <div className="muted small">
                {doc.user} (clearance {doc.clearance}) · {doc.mode} {doc.llm_model ? `· ${doc.llm_model}` : ""} · answer <TlpBadge tlp={doc.answer_tlp} />
              </div>
              <p className="answer-text">{doc.answer}</p>
              <div className="small muted">
                {doc.hops.length} hops · {doc.chunks.length} chunks · {doc.documents.length} documents · {doc.iocs.length} IOC states · citations {doc.citations.join(" ")}
              </div>
              <button className="primary" onClick={replay}>
                Replay against the stores
              </button>
              {rep && (
                <div className="replay">
                  <div className="row">
                    <span>hops {rep.summary.hops_verified}</span>
                    <span>chunks {rep.summary.chunks_verified}</span>
                    <span>documents {rep.summary.documents_verified}</span>
                    <span>IOC state changes {rep.summary.ioc_state_changes}</span>
                  </div>
                  <h4>Graph hops (Neo4j)</h4>
                  <ul className="list small mono">
                    {rep.hops.map((h) => (
                      <li key={h.cid}>
                        {ok(h.still_exists)} [{h.cid}] {h.source} -[{h.type}]-&gt; {h.target}
                      </li>
                    ))}
                  </ul>
                  <h4>Chunks (Qdrant)</h4>
                  <ul className="list small">
                    {rep.chunks.map((c) => (
                      <li key={c.cid}>
                        {ok(c.still_exists)} [{c.cid}] point {c.point_id} → {c.report_id} (score {c.score})
                      </li>
                    ))}
                  </ul>
                  <h4>Documents (MongoDB + Report node)</h4>
                  <ul className="list small">
                    {rep.documents.map((d) => (
                      <li key={d._id}>
                        {ok(d.in_mongodb && d.has_report_node)} {d._id} <TlpBadge tlp={d.tlp} />
                      </li>
                    ))}
                  </ul>
                  <h4>IOC state (Redis) — then vs now</h4>
                  <ul className="list small mono">
                    {rep.iocs.map((i) => (
                      <li key={i.cid}>
                        [{i.cid}] {i.value}: {i.state} → {i.state_now} {i.changed && <span className="caution-inline">changed</span>}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
