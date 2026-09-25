export default function Json({ value }) {
  return <pre className="json">{JSON.stringify(value, null, 2)}</pre>;
}
