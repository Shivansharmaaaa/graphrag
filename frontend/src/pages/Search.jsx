import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api.js";
import ErrorBox from "../components/ErrorBox.jsx";
import SimilarityMap from "../components/SimilarityMap.jsx";
import TlpBadge from "../components/TlpBadge.jsx";

const EXAMPLES = [
  "supply-chain compromise of signed software updates",
  "spearphishing against political organisations",
  "wiper disguised as ransomware",
  "help desk social engineering to reset MFA",
];

export default function Search() {
  const nav = useNavigate();
  const [query, setQuery] = useState(EXAMPLES[0]);
  const [k, setK] = useState(8);
  const [actors, setActors] = useState("");
  const [tlp, setTlp] = useState({ WHITE: true, GREEN: true, AMBER: true, RED: true });
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [res, setRes] = useState(null);
  const [err, setErr] = useState(null);

  const run = async (q = query) => {
    setQuery(q);
    setErr(null);
    try {
      setRes(
        await api("/search/semantic", {
          method: "POST",
          body: {
            query: q,
            k,
            actors: actors ? actors.split(",").map((s) => s.trim()).filter(Boolean) : null,
            tlp: Object.keys(tlp).filter((t) => tlp[t]),
            date_from: from || null,
            date_to: to || null,
          },
        })
      );
    } catch (e) {
      setErr(e);
    }
  };

  return (
    <div className="page">
      <h1>Semantic search</h1>
      <p className="lede">
        Qdrant k-NN over report chunks (cosine, HNSW). Payload filters (actor, TLP, date) only restrict the candidate set. Nearest neighbour ≠ shared infrastructure:
        use the graph for relationships.
      </p>
      <div className="card">
        <form className="row" onSubmit={(e) => (e.preventDefault(), run())}>
          <input style={{ flex: 3 }} value={query} onChange={(e) => setQuery(e.target.value)} />
          <label className="inline">
            k <input type="number" min={1} max={30} value={k} onChange={(e) => setK(+e.target.value)} style={{ width: 56 }} />
          </label>
          <button className="primary">Search</button>
        </form>
        <div className="row small">
          <input placeholder="actors filter, e.g. apt28,apt29" value={actors} onChange={(e) => setActors(e.target.value)} />
          {Object.keys(tlp).map((t) => (
            <label key={t} className="inline">
              <input type="checkbox" checked={tlp[t]} onChange={(e) => setTlp({ ...tlp, [t]: e.target.checked })} /> {t}
            </label>
          ))}
          <label className="inline">
            from <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
          </label>
          <label className="inline">
            to <input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
          </label>
        </div>
        <div className="chips">
          {EXAMPLES.map((x) => (
            <button key={x} className="chip" onClick={() => run(x)}>
              {x}
            </button>
          ))}
        </div>
      </div>
      <ErrorBox error={err} />
      {res && (
        <div className="split">
          <div className="card">
            <h3>Hits</h3>
            {res.hits.length === 0 && <div className="muted">No chunks match these filters (TLP above your clearance is always excluded).</div>}
            {res.hits.map((h) => (
              <div key={h.point_id} className="chunk">
                <div className="chunk-head">
                  <span className="score">cos {h.score}</span> <Link to={`/reports/${h.report_id}`}>{h.title}</Link> <TlpBadge tlp={h.tlp} />
                  <span className="muted small">
                    {" "}
                    · {h.date} · chunk {h.chunk_index} · point {h.point_id} · actors {h.actors.join(", ")}
                  </span>
                </div>
                <div className="chunk-text">{h.text}</div>
              </div>
            ))}
          </div>
          <div className="card">
            <h3>Similarity neighbourhood</h3>
            <div className="muted small">★ query · teal = k-NN hits · grey = other chunks (2-D PCA of the vectors). Click a hit to open its report.</div>
            <SimilarityMap points={res.map} height={420} onPick={(id) => nav(`/reports/${id}`)} />
          </div>
        </div>
      )}
    </div>
  );
}
