import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import ErrorBox from "../components/ErrorBox.jsx";
import GraphCanvas from "../components/GraphCanvas.jsx";
import SimilarityMap from "../components/SimilarityMap.jsx";
import TlpBadge from "../components/TlpBadge.jsx";
import Ttl from "../components/Ttl.jsx";

const TAG_RE = /\[(G\d+|C\d+|I\d+|R:[\w.\-]+)\]/g;

function Answer({ text, onCite, active }) {
  const parts = [];
  let last = 0;
  for (const m of text.matchAll(TAG_RE)) {
    parts.push(text.slice(last, m.index));
    const id = m[1];
    parts.push(
      <button key={m.index} className={`cite cite-${id[0]} ${active === id ? "on" : ""}`} onClick={() => onCite(id)}>
        {id}
      </button>
    );
    last = m.index + m[0].length;
  }
  parts.push(text.slice(last));
  return <p className="answer-text">{parts}</p>;
}

export function EvidencePanel({ res, active, setActive }) {
  const [tab, setTab] = useState("graph");
  const [fetchedAt, setFetchedAt] = useState(Date.now());
  useEffect(() => setFetchedAt(Date.now()), [res]);
  useEffect(() => {
    if (!active) return;
    setTab({ G: "graph", C: "chunks", I: "iocs", R: "docs" }[active[0]]);
    setTimeout(() => document.getElementById(`ev-${active}`)?.scrollIntoView({ block: "nearest", behavior: "smooth" }), 60);
  }, [active]);

  const ev = res.evidence;
  const cited = new Set(res.citations);
  const highlight = useMemo(
    () => new Set(ev.graph.edges.filter((e) => cited.has(e.cid) || active === e.cid).map((e) => `${e.source}|${e.type}|${e.target}`)),
    [res, active]
  );
  const tabs = [
    ["graph", `Graph hops (${ev.facts.length})`],
    ["chunks", `Chunks (${ev.chunks.length})`],
    ["docs", `Documents (${ev.documents.length})`],
    ["iocs", `IOC state (${ev.iocs.length})`],
    ["latency", "Latency"],
  ];
  return (
    <div className="card evidence">
      <div className="tabs">
        {tabs.map(([k, l]) => (
          <button key={k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>
            {l}
          </button>
        ))}
      </div>
      {tab === "graph" && (
        <>
          <GraphCanvas data={ev.graph} height={330} highlight={highlight} animate />
          <div className="muted small">Cited hops light up in order. Seeds: {res.seeds.join(", ") || "—"} ({res.seed_source})</div>
          <ul className="facts">
            {ev.facts.map((f) => (
              <li key={f.cid} id={`ev-${f.cid}`} className={`${cited.has(f.cid) ? "cited" : ""} ${active === f.cid ? "active" : ""}`}>
                <code>[{f.cid}]</code> {f.text}
              </li>
            ))}
          </ul>
        </>
      )}
      {tab === "chunks" && (
        <>
          <SimilarityMap points={ev.similarity_map} height={220} />
          {ev.chunks.map((c) => (
            <div key={c.cid} id={`ev-${c.cid}`} className={`chunk ${cited.has(c.cid) ? "cited" : ""} ${active === c.cid ? "active" : ""}`}>
              <div className="chunk-head">
                <code>[{c.cid}]</code> <Link to={`/reports/${c.report_id}`}>{c.report_id}</Link> · {c.title}
                <span className="score">cos {c.score}</span> <TlpBadge tlp={c.tlp} />
              </div>
              <div className="chunk-text">{c.text}</div>
            </div>
          ))}
          {ev.orphan_chunks_refused?.length > 0 && (
            <div className="warn">Refused chunks without a Report node: {ev.orphan_chunks_refused.join(", ")}</div>
          )}
        </>
      )}
      {tab === "docs" && (
        <>
          {ev.documents.map((d) => (
            <div key={d._id} id={`ev-R:${d._id}`} className={`doc-row ${cited.has(`R:${d._id}`) ? "cited" : ""} ${active === `R:${d._id}` ? "active" : ""}`}>
              <Link to={`/reports/${d._id}`}>
                <b>{d._id}</b>
              </Link>{" "}
              {d.title} <TlpBadge tlp={d.tlp} />
              <div className="muted small">
                {d.date} · {d.source} · actors: {d.actors.join(", ") || "—"} · report-specific fields:{" "}
                {d.variable_fields.join(", ") || "none"}
              </div>
            </div>
          ))}
          {ev.withheld_by_tlp > 0 && <div className="warn">{ev.withheld_by_tlp} document(s) withheld by TLP policy.</div>}
        </>
      )}
      {tab === "iocs" && (
        <>
          {!ev.redis_available && <div className="warn">Redis unavailable — IOC state unknown (read path degraded).</div>}
          <table className="tbl">
            <thead>
              <tr>
                <th />
                <th>Indicator</th>
                <th>State</th>
                <th>TTL</th>
                <th>Severity</th>
              </tr>
            </thead>
            <tbody>
              {ev.iocs.map((x) => (
                <tr key={x.cid} id={`ev-${x.cid}`} className={`${cited.has(x.cid) ? "cited" : ""} ${active === x.cid ? "active" : ""}`}>
                  <td>
                    <code>{x.cid}</code>
                  </td>
                  <td className="mono">{x.value}</td>
                  <td>
                    <span className={`state state-${x.state.split(" ")[0]}`}>{x.state}</span>
                  </td>
                  <td>{x.state === "live" ? <Ttl ttl={x.ttl_remaining} fetchedAt={fetchedAt} total={x.ttl} /> : "—"}</td>
                  <td>{x.severity || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
      {tab === "latency" && (
        <table className="tbl">
          <tbody>
            {Object.entries(res.latency_ms).map(([k, v]) => (
              <tr key={k}>
                <td>{k}</td>
                <td className="mono">{v} ms</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {active && (
        <button className="link small" onClick={() => setActive(null)}>
          clear citation focus
        </button>
      )}
    </div>
  );
}

export default function GraphRAG() {
  const [meta, setMeta] = useState(null);
  const [q, setQ] = useState("");
  const [hops, setHops] = useState(2);
  const [k, setK] = useState(6);
  const [useLlm, setUseLlm] = useState(true);
  const [res, setRes] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [active, setActive] = useState(null);

  useEffect(() => {
    api("/meta").then(setMeta).catch(setErr);
  }, []);

  const ask = async (question = q) => {
    if (!question.trim()) return;
    setQ(question);
    setBusy(true);
    setErr(null);
    setActive(null);
    try {
      setRes(await api("/graphrag/ask", { method: "POST", body: { question, max_hops: hops, k, use_llm: useLlm } }));
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page">
      <h1>GraphRAG console</h1>
      <p className="lede">
        Ask a natural-language question. Retrieval runs over all four stores (Qdrant k-NN → Neo4j expansion → MongoDB hydration → Redis IOC state), then a
        locally hosted LLM renders the evidence. Sentences without a valid citation are removed.
      </p>
      <div className="card">
        <textarea rows={2} value={q} placeholder="e.g. Which actors share C2 infrastructure with APT28, and which reports discuss that overlap?" onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && (e.preventDefault(), ask())} />
        <div className="row">
          <label className="inline">
            hops
            <select value={hops} onChange={(e) => setHops(+e.target.value)}>
              {[1, 2, 3].map((h) => (
                <option key={h}>{h}</option>
              ))}
            </select>
          </label>
          <label className="inline">
            top-k chunks
            <input type="number" min={1} max={20} value={k} onChange={(e) => setK(+e.target.value)} style={{ width: 60 }} />
          </label>
          <label className="inline">
            <input type="checkbox" checked={useLlm} onChange={(e) => setUseLlm(e.target.checked)} /> use local LLM ({meta?.llm_model || "…"})
          </label>
          <button className="primary" onClick={() => ask()} disabled={busy}>
            {busy ? "Retrieving…" : "Ask"}
          </button>
        </div>
        <div className="chips">
          {meta?.demo_queries.map((d) => (
            <button key={d} className="chip" onClick={() => ask(d)}>
              {d}
            </button>
          ))}
        </div>
      </div>
      <ErrorBox error={err} />
      {res && (
        <div className="split">
          <div className="card answer">
            <div className="answer-meta">
              <span className={`mode ${res.mode === "llm" ? "llm" : "ro"}`}>{res.mode}</span>
              <TlpBadge tlp={res.answer_tlp} />
              <span className="muted small">
                citation coverage {(res.citation_coverage * 100).toFixed(0)}% · {res.latency_ms.total} ms ·{" "}
                <Link to={`/audit/${res.id}`}>audit {res.id}</Link>
              </span>
            </div>
            {res.refused && <div className="warn">Refused: the answer could not be grounded in the retrieved evidence.</div>}
            <Answer text={res.answer} onCite={setActive} active={active} />
            {res.llm_error && <div className="muted small">LLM unavailable → retrieve-only mode ({res.llm_error})</div>}
            {res.evidence.hub_notes.map((h) => (
              <div key={h} className="caution">
                ⚠ {h}
              </div>
            ))}
            {res.dropped_sentences.length > 0 && (
              <details>
                <summary>{res.dropped_sentences.length} uncited sentence(s) removed by the groundedness gate</summary>
                <ul>
                  {res.dropped_sentences.map((s, i) => (
                    <li key={i} className="muted">
                      {s}
                    </li>
                  ))}
                </ul>
              </details>
            )}
            <div className="muted small">
              Linked entities: {res.linked_entities.map((e) => `${e.name} (${e.label})`).join(", ") || "none — seeded from vector hits"}
            </div>
          </div>
          <EvidencePanel res={res} active={active} setActive={setActive} />
        </div>
      )}
    </div>
  );
}
