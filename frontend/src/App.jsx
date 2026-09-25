import { createContext, useContext, useEffect, useState } from "react";
import { Navigate, NavLink, Route, Routes, useNavigate } from "react-router-dom";
import { api, session } from "./api.js";
import TlpBadge from "./components/TlpBadge.jsx";
import Login from "./pages/Login.jsx";
import GraphRAG from "./pages/GraphRAG.jsx";
import GraphExplorer from "./pages/GraphExplorer.jsx";
import Reports from "./pages/Reports.jsx";
import Blocklist from "./pages/Blocklist.jsx";
import Search from "./pages/Search.jsx";
import Ingest from "./pages/Ingest.jsx";
import Audit from "./pages/Audit.jsx";
import Ops from "./pages/Ops.jsx";

const UserCtx = createContext(null);
export const useUser = () => useContext(UserCtx);
export const ROLE_RANK = { analyst: 0, lead: 1, admin: 2 };
export const hasRole = (user, role) => ROLE_RANK[user?.role] >= ROLE_RANK[role];

const NAV = [
  ["/", "GraphRAG console"],
  ["/graph", "Graph explorer"],
  ["/reports", "Report browser"],
  ["/blocklist", "IOC blocklist"],
  ["/search", "Semantic search"],
  ["/ingest", "Ingest"],
  ["/audit", "Audit & replay"],
  ["/ops", "Operations"],
];

function HealthStrip() {
  const [h, setH] = useState(null);
  useEffect(() => {
    let alive = true;
    const load = () => api("/health").then((d) => alive && setH(d)).catch(() => alive && setH(null));
    load();
    const t = setInterval(load, 10000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);
  const stores = ["neo4j", "mongodb", "redis", "qdrant", "llm"];
  return (
    <div className="health-strip">
      {stores.map((s) => {
        const st = h?.stores?.[s];
        return (
          <span key={s} className={`dot ${st ? (st.ok ? "ok" : "bad") : "unk"}`} title={st?.detail || "unknown"}>
            {s}
          </span>
        );
      })}
    </div>
  );
}

function Shell({ user, onLogout }) {
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">◈</div>
          <div>
            <div className="brand-title">CTI Workstation</div>
            <div className="brand-sub">GraphRAG · polyglot NoSQL</div>
          </div>
        </div>
        <nav>
          {NAV.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => (isActive ? "active" : "")}>
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          <HealthStrip />
          <div className="whoami">
            <div>{user.display}</div>
            <div className="muted small">
              {user.username} · {user.role} · clearance <TlpBadge tlp={user.clearance} />
            </div>
            <button className="link" onClick={onLogout}>
              Sign out
            </button>
          </div>
        </div>
      </aside>
      <main className="content">
        <Routes>
          <Route path="/" element={<GraphRAG />} />
          <Route path="/graph" element={<GraphExplorer />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/reports/:id" element={<Reports />} />
          <Route path="/blocklist" element={<Blocklist />} />
          <Route path="/search" element={<Search />} />
          <Route path="/ingest" element={<Ingest />} />
          <Route path="/audit" element={<Audit />} />
          <Route path="/audit/:id" element={<Audit />} />
          <Route path="/ops" element={<Ops />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState(session.user);
  const nav = useNavigate();
  const logout = () => {
    session.clear();
    setUser(null);
    nav("/login");
  };
  return (
    <UserCtx.Provider value={user}>
      <Routes>
        <Route
          path="/login"
          element={
            <Login
              onLogin={(u) => {
                setUser(u);
                nav("/");
              }}
            />
          }
        />
        <Route path="/*" element={user ? <Shell user={user} onLogout={logout} /> : <Navigate to="/login" />} />
      </Routes>
    </UserCtx.Provider>
  );
}
