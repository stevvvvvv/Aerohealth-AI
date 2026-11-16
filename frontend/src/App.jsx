import { NavLink, Route, Routes } from "react-router-dom";
import Fleet from "./pages/Fleet.jsx";
import EngineView from "./pages/EngineView.jsx";
import Alerts from "./pages/Alerts.jsx";
import Model from "./pages/Model.jsx";

export default function App() {
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <svg viewBox="0 0 32 32" width="26" height="26" aria-hidden>
            <circle cx="16" cy="16" r="13" fill="none" stroke="#3987e5" strokeWidth="2.5" />
            <path d="M16 5v22M5 16h22M8.2 8.2l15.6 15.6M23.8 8.2 8.2 23.8" stroke="#3987e5" strokeWidth="1.4" />
            <circle cx="16" cy="16" r="3.2" fill="#3987e5" />
          </svg>
          <div>
            <strong>AeroHealth</strong>
            <span>AI</span>
          </div>
        </div>
        <nav>
          <NavLink to="/" end>Fleet</NavLink>
          <NavLink to="/alerts">Alerts</NavLink>
          <NavLink to="/model">Model card</NavLink>
        </nav>
        <footer className="muted small">
          NASA C-MAPSS · FD001
          <br />
          Turbofan degradation simulation
        </footer>
      </aside>
      <main className="content">
        <Routes>
          <Route path="/" element={<Fleet />} />
          <Route path="/engines/:id" element={<EngineView />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="/model" element={<Model />} />
        </Routes>
      </main>
    </div>
  );
}
