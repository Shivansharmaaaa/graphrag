import { useState } from "react";
import { api, session } from "../api.js";
import ErrorBox from "../components/ErrorBox.jsx";

const DEMO = [
  ["analyst", "analyst123", "SOC analyst · AMBER"],
  ["junior", "junior123", "Junior analyst · GREEN"],
  ["lead", "lead123", "CTI lead · RED · can publish IOCs / ingest"],
  ["admin", "admin123", "Platform operator · RED · seed / reindex"],
];

export default function Login({ onLogin }) {
  const [username, setU] = useState("analyst");
  const [password, setP] = useState("analyst123");
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e?.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const r = await api("/auth/login", { method: "POST", body: { username, password } });
      session.save(r.token, r.user);
      onLogin(r.user);
    } catch (e2) {
      setErr(e2);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login">
      <form className="card login-card" onSubmit={submit}>
        <div className="brand">
          <div className="brand-mark">◈</div>
          <div>
            <div className="brand-title">CTI Workstation</div>
            <div className="brand-sub">GraphRAG · Neo4j · MongoDB · Redis · Qdrant</div>
          </div>
        </div>
        <label>
          Username
          <input value={username} onChange={(e) => setU(e.target.value)} autoFocus />
        </label>
        <label>
          Password
          <input type="password" value={password} onChange={(e) => setP(e.target.value)} />
        </label>
        <ErrorBox error={err} />
        <button className="primary" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
        <div className="muted small" style={{ marginTop: 12 }}>
          Demo accounts (change in production):
          <ul className="demo-users">
            {DEMO.map(([u, p, d]) => (
              <li key={u}>
                <button type="button" className="link" onClick={() => { setU(u); setP(p); }}>
                  {u}
                </button>{" "}
                — {d}
              </li>
            ))}
          </ul>
        </div>
      </form>
    </div>
  );
}
