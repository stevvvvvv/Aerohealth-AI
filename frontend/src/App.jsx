import { NavLink, Route, Routes } from "react-router-dom";
import Fleet from "./pages/Fleet.jsx";
import EngineView from "./pages/EngineView.jsx";
import Alerts from "./pages/Alerts.jsx";
import Model from "./pages/Model.jsx";
import { STATIC, api } from "./api.js";
import { useFetch } from "./useFetch.js";
import { STATUS } from "./theme.js";

function Memo() {
  const { data } = useFetch(api.fleet);
  if (!data) return null;
  return (
    <div className="memo" aria-label="Fleet status">
      {["CRITICAL", "WARNING", "WATCH", "HEALTHY"].map((s) => (
        <span key={s} className="memo-item" title={`${STATUS[s].label} engines`}>
          <span style={{ color: STATUS[s].color }} aria-hidden>{STATUS[s].icon}</span>
          <b>{data.counts[s] || 0}</b>
          <span className="sr-only">{STATUS[s].label}</span>
        </span>
      ))}
    </div>
  );
}

export default function App() {
  return (
    <>
      <header className="topbar">
        <NavLink to="/" className="brand" aria-label="AeroHealth AI home">
          <svg viewBox="0 0 32 32" width="24" height="24" aria-hidden>
            <circle cx="16" cy="16" r="13" fill="none" stroke="#4cc3df" strokeWidth="2" />
            <g stroke="#4cc3df" strokeWidth="1.6" strokeLinecap="round">
              {[0, 45, 90, 135, 180, 225, 270, 315].map((a) => (
                <line key={a} x1="16" y1="16" x2={16 + 10 * Math.cos((a * Math.PI) / 180)} y2={16 + 10 * Math.sin((a * Math.PI) / 180)} />
              ))}
            </g>
            <circle cx="16" cy="16" r="3.5" fill="#0b141c" stroke="#4cc3df" strokeWidth="1.6" />
          </svg>
          AeroHealth <span>AI</span>
        </NavLink>
        <nav className="tabs">
          <NavLink to="/" end>Fleet</NavLink>
          <NavLink to="/alerts">Alerts</NavLink>
          <NavLink to="/model">Model</NavLink>
        </nav>
        <Memo />
      </header>
      <main className="content">
        {STATIC && (
          <p className="demo-banner">
            Static demo of the NASA C-MAPSS FD001 test fleet: every value comes from the trained models, precomputed.
            Explanations are available every 10 cycles. <a href="https://github.com/stevvvvvv/Aerohealth-AI">Run it live with Docker</a>
          </p>
        )}
        <Routes>
          <Route path="/" element={<Fleet />} />
          <Route path="/engines/:id" element={<EngineView />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="/model" element={<Model />} />
        </Routes>
      </main>
    </>
  );
}
