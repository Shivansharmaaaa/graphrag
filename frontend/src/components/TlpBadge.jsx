export default function TlpBadge({ tlp }) {
  const t = (tlp || "WHITE").toUpperCase();
  return <span className={`tlp tlp-${t.toLowerCase()}`}>TLP:{t === "WHITE" ? "CLEAR" : t}</span>;
}
