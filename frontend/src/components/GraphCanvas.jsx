import { useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";

export const LABEL_COLORS = {
  ThreatActor: "#e5484d",
  Campaign: "#f5a524",
  Malware: "#b57bff",
  Infrastructure: "#2bb3a3",
  Technique: "#6e9cff",
  Indicator: "#e7c24a",
  Victim: "#4cc38a",
  Report: "#9aa4b2",
};

/**
 * Force-directed view of a subgraph.
 * `highlight` = Set of "source|TYPE|target" keys to emphasise (cited hops);
 * `animate` = true replays highlighted hops one by one (GraphRAG evidence).
 */
export default function GraphCanvas({ data, height = 520, onNodeClick, highlight, animate = false, selected }) {
  const wrap = useRef(null);
  const fg = useRef(null);
  const [width, setWidth] = useState(600);
  const [step, setStep] = useState(Infinity);

  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setWidth(el.clientWidth));
    ro.observe(el);
    setWidth(el.clientWidth);
    return () => ro.disconnect();
  }, []);

  const graphData = useMemo(() => {
    const nodes = (data?.nodes || []).map((n) => ({ ...n }));
    const ids = new Set(nodes.map((n) => n.id));
    const links = (data?.edges || [])
      .filter((e) => ids.has(e.source) && ids.has(e.target))
      .map((e) => ({ source: e.source, target: e.target, type: e.type, cid: e.cid, key: `${e.source}|${e.type}|${e.target}` }));
    return { nodes, links };
  }, [data]);

  const hlOrder = useMemo(() => graphData.links.filter((l) => highlight?.has(l.key)).map((l) => l.key), [graphData, highlight]);

  useEffect(() => {
    if (!animate || !hlOrder.length) {
      setStep(Infinity);
      return;
    }
    setStep(0);
    const t = setInterval(() => setStep((s) => (s >= hlOrder.length ? s : s + 1)), 350);
    return () => clearInterval(t);
  }, [animate, hlOrder]);

  useEffect(() => {
    const t = setTimeout(() => fg.current?.zoomToFit(400, 40), 700);
    return () => clearTimeout(t);
  }, [graphData]);

  const lit = useMemo(() => new Set(hlOrder.slice(0, step)), [hlOrder, step]);

  return (
    <div ref={wrap} className="graph-wrap" style={{ height }}>
      <ForceGraph2D
        ref={fg}
        width={width}
        height={height}
        graphData={graphData}
        backgroundColor="rgba(0,0,0,0)"
        cooldownTicks={120}
        linkDirectionalArrowLength={4}
        linkDirectionalArrowRelPos={0.9}
        linkColor={(l) => (lit.has(l.key) ? "#ffd166" : highlight?.size ? "rgba(140,150,170,0.18)" : "rgba(160,170,190,0.45)")}
        linkWidth={(l) => (lit.has(l.key) ? 2.6 : 1)}
        linkDirectionalParticles={(l) => (lit.has(l.key) ? 2 : 0)}
        linkDirectionalParticleWidth={3}
        linkLabel={(l) => `${l.type}${l.cid ? ` [${l.cid}]` : ""}`}
        nodeLabel={(n) => `${n.label}: ${n.name}`}
        onNodeClick={onNodeClick}
        nodeCanvasObject={(node, ctx, scale) => {
          const r = node.label === "ThreatActor" ? 7 : node.label === "Report" ? 4 : 5.5;
          ctx.beginPath();
          ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
          ctx.fillStyle = LABEL_COLORS[node.label] || "#ccc";
          ctx.fill();
          if (selected === node.id) {
            ctx.lineWidth = 2;
            ctx.strokeStyle = "#fff";
            ctx.stroke();
          }
          const fs = Math.max(10 / scale, 2.5);
          if (scale > 0.9 || node.label === "ThreatActor") {
            ctx.font = `${fs}px Inter, system-ui, sans-serif`;
            ctx.fillStyle = "#d6dbe4";
            ctx.textAlign = "center";
            const name = String(node.name || node.id);
            ctx.fillText(name.length > 26 ? name.slice(0, 25) + "…" : name, node.x, node.y + r + fs);
          }
        }}
      />
      <div className="legend">
        {Object.entries(LABEL_COLORS).map(([k, c]) => (
          <span key={k}>
            <i style={{ background: c }} />
            {k}
          </span>
        ))}
      </div>
    </div>
  );
}
