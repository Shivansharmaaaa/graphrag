import { useEffect, useState } from "react";
import { api, qs } from "../api.js";
import ErrorBox from "../components/ErrorBox.jsx";
import GraphCanvas from "../components/GraphCanvas.jsx";
import Json from "../components/Json.jsx";

const PRESETS = {
  infra: "Shared infrastructure (USES_INFRA)",
  tooling: "Shared tooling (USES)",
  victims: "Common victims",
  path: "Shortest path",
};

export default function GraphExplorer() {
  const [data, setData] = useState(null);
  const [sel, setSel] = useState(null);
  const [hops, setHops] = useState(1);
  const [q, setQ] = useState("");
  const [hits, setHits] = useState([]);
  const [actors, setActors] = useState([]);
  const [preset, setPreset] = useState("infra");
  const [pa, setPa] = useState("apt28");
  const [pb, setPb] = useState("fin7");
  const [rows, setRows] = useState(null);
  const [err, setErr] = useState(null);

  const run = (p) => p.catch(setErr);

  useEffect(() => {
    run(api("/graph/overview").then(setData));
    run(api("/graph/search?label=ThreatActor&limit=100").then(setActors));
  }, []);

  const openNode = (id, h = hops) =>
    run(
      api(`/graph/node/${encodeURIComponent(id)}?hops=${h}`).then((r) => {
        setSel(r.node);
        setData(r.subgraph.nodes.length ? r.subgraph : { nodes: [r.node], edges: [] });
      })
    );

  const search = (e) => {
    e.preventDefault();
    run(api(`/graph/search${qs({ q })}`).then(setHits));
  };

  const runPreset = () => {
    setErr(null);
    const a = pa || undefined;
    if (preset === "infra") return run(api(`/graph/shared-infrastructure${qs({ actor: a })}`).then(setRows));
    if (preset === "tooling") return run(api(`/graph/shared-tooling${qs({ actor: a })}`).then(setRows));
    if (preset === "victims") return run(api(`/graph/common-victims${qs({ actor: a })}`).then(setRows));
    return run(
      api(`/graph/path${qs({ src: pa, dst: pb })}`).then((g) => {
        setRows(null);
        if (!g.nodes.length) setErr(new Error("no path within 4 hops"));
        else setData(g);
      })
    );
  };

  return (
    <div className="page">
      <h1>Graph explorer</h1>
      <p className="lede">Neo4j is the system of record for relationships. Multi-hop traversals stop at commodity hubs (e.g. Mimikatz, Cobalt Strike) rather than walking through them.</p>
      <div className="split wide-left">
        <div className="card">
          <div className="row">
            <button onClick={() => run(api("/graph/overview").then(setData)) && setSel(null)}>Whole graph</button>
            {sel && (
              <>
                <span className="muted">Neighbourhood of <b>{sel.name}</b></span>
                <select value={hops} onChange={(e) => { setHops(+e.target.value); openNode(sel.id, +e.target.value); }}>
                  {[1, 2, 3].map((h) => (
                    <option key={h} value={h}>{h} hop{h > 1 ? "s" : ""}</option>
                  ))}
                </select>
              </>
            )}
            <span className="muted small">{data ? `${data.nodes.length} nodes · ${data.edges.length} edges` : ""}</span>
          </div>
          <GraphCanvas data={data} height={560} onNodeClick={(n) => openNode(n.id)} selected={sel?.id} />
        </div>
        <div className="stack">
          <form className="card" onSubmit={search}>
            <h3>Find entity</h3>
            <div className="row">
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="APT28, Cobalt Strike, 185.86.77.12…" />
              <button>Search</button>
            </div>
            <ul className="list">
              {hits.map((h) => (
                <li key={h.id}>
                  <button className="link" onClick={() => openNode(h.id)}>{h.name}</button> <span className="muted small">{h.label}</span>
                </li>
              ))}
            </ul>
          </form>
          <div className="card">
            <h3>Path queries</h3>
            <select value={preset} onChange={(e) => setPreset(e.target.value)}>
              {Object.entries(PRESETS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
            <div className="row">
              {preset === "path" ? (
                <>
                  <input value={pa} onChange={(e) => setPa(e.target.value)} placeholder="from id" />
                  <input value={pb} onChange={(e) => setPb(e.target.value)} placeholder="to id" />
                </>
              ) : (
                <select value={pa} onChange={(e) => setPa(e.target.value)}>
                  <option value="">(all actors)</option>
                  {actors.map((a) => (
                    <option key={a.id} value={a.id}>{a.name}</option>
                  ))}
                </select>
              )}
              <button className="primary" onClick={runPreset}>Run</button>
            </div>
            {rows && (
              <table className="tbl small">
                <tbody>
                  {rows.length === 0 && <tr><td className="muted">no results</td></tr>}
                  {rows.map((r, i) => (
                    <tr key={i}>
                      <td>
                        <b>{r.actor_name}</b> ↔ <b>{r.other_name}</b>
                        <div className="muted">
                          {preset === "infra" && <>via {r.kind} <span className="mono">{r.infra}</span>{r.hosted_malware?.length ? ` · hosted ${r.hosted_malware.join(", ")}` : ""}{r.reports?.length ? ` · reports ${r.reports.join(", ")}` : ""}</>}
                          {preset === "tooling" && <>via {r.malware} ({r.kind}){r.commodity_hub && <span className="caution-inline"> commodity hub — weak attribution ({r.users} actors)</span>}</>}
                          {preset === "victims" && <>{r.victims.join(", ")} ({r.sectors.join(", ")})</>}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          {sel && (
            <div className="card">
              <h3>{sel.label}: {sel.name}</h3>
              <div className="muted small">degree {sel.degree}</div>
              <Json value={sel.props} />
            </div>
          )}
          <ErrorBox error={err} />
        </div>
      </div>
    </div>
  );
}
