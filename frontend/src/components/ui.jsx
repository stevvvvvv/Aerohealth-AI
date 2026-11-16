import { STATUS } from "../theme.js";

export function StatusBadge({ status }) {
  const s = STATUS[status] || STATUS.HEALTHY;
  return (
    <span className="badge" style={{ "--c": s.color }}>
      <span className="badge-icon" aria-hidden>{s.icon}</span>
      {s.label}
    </span>
  );
}

export function LevelBadge({ level }) {
  return <StatusBadge status={level} />;
}

export function Stat({ label, value, sub, accent }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value" style={accent ? { color: accent } : undefined}>{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

export function Card({ title, subtitle, actions, children }) {
  return (
    <section className="card">
      {(title || actions) && (
        <header className="card-head">
          <div>
            <h3>{title}</h3>
            {subtitle && <p className="muted small">{subtitle}</p>}
          </div>
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}

export function Loading({ error }) {
  if (error) return <div className="state error">Could not load data — {String(error.message || error)}</div>;
  return <div className="state">Loading…</div>;
}

export function HealthBar({ value }) {
  if (value == null) return <span className="muted">—</span>;
  const pct = Math.round(value * 100);
  return (
    <div className="hbar" title={`Health index ${pct}%`}>
      <div className="hbar-fill" style={{ width: `${pct}%` }} />
      <span>{pct}%</span>
    </div>
  );
}

export const fmt = (v, d = 0) => (v == null ? "—" : Number(v).toFixed(d));
export const pct = (v) => (v == null ? "—" : `${Math.round(v * 100)}%`);
