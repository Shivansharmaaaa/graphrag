export default function ErrorBox({ error }) {
  if (!error) return null;
  return <div className="error">{error.message || String(error)}</div>;
}
