import { CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from "recharts";

// 2-D PCA projection of the query vector, its k-NN hits and a background sample of the collection.
export default function SimilarityMap({ points, height = 300, onPick }) {
  if (!points?.length) return <div className="empty">No vectors to plot.</div>;
  const q = points.filter((p) => p.kind === "query");
  const hits = points.filter((p) => p.kind === "hit");
  const bg = points.filter((p) => p.kind === "corpus");
  const tip = ({ active, payload }) =>
    active && payload?.length ? (
      <div className="chart-tip">
        <b>{payload[0].payload.kind}</b>
        <div>{payload[0].payload.label}</div>
        {payload[0].payload.score !== undefined && <div>cosine {payload[0].payload.score}</div>}
      </div>
    ) : null;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ScatterChart margin={{ top: 10, right: 10, bottom: 10, left: 0 }}>
        <CartesianGrid stroke="#263042" />
        <XAxis type="number" dataKey="x" hide />
        <YAxis type="number" dataKey="y" hide />
        <ZAxis range={[60, 60]} />
        <Tooltip content={tip} />
        <Scatter data={bg} fill="#4a5568" />
        <Scatter data={hits} fill="#2bb3a3" onClick={(p) => onPick?.(p.report_id)} cursor="pointer" />
        <Scatter data={q} fill="#ffd166" shape="star" />
      </ScatterChart>
    </ResponsiveContainer>
  );
}
