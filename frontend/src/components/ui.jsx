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

export const LevelBadge = ({ level }) => <StatusBadge status={level} />;

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
            {subtitle && <p>{subtitle}</p>}
          </div>
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}

export function Loading({ error }) {
  if (error) return <div className="state error">Could not load data: {String(error.message || error)}</div>;
  return <div className="state">Loading…</div>;
}

export function HealthBar({ value }) {
  if (value == null) return <span className="muted">—</span>;
  const pct = Math.round(value * 100);
  const color = value > 0.6 ? STATUS.HEALTHY.color : value > 0.25 ? STATUS.WATCH.color : STATUS.WARNING.color;
  return (
    <div className="hcell" title={`Health index ${pct}%`}>
      <div className="hbar"><div className="hbar-fill" style={{ width: `${pct}%`, background: color }} /></div>
      <span>{pct}%</span>
    </div>
  );
}

/** Predicted RUL with its 90% interval on a 0–125 cycle scale. */
export function RangeBar({ mean, lower, upper, status }) {
  if (mean == null) return <span className="muted">—</span>;
  const x = (v) => `${(Math.min(Math.max(v, 0), 125) / 125) * 100}%`;
  return (
    <div className="range" title={`RUL ${Math.round(mean)} cycles, 90% interval ${Math.round(lower)}–${Math.round(upper)}`}>
      <div className="range-track" />
      <div className="range-zone" style={{ left: x(lower), width: `calc(${x(upper)} - ${x(lower)})`, background: `${STATUS[status]?.color || "#1b98b8"}88` }} />
      <div className="range-mean" style={{ left: x(mean) }} />
    </div>
  );
}

export const fmt = (v, d = 0) => (v == null ? "—" : Number(v).toFixed(d));
export const pct = (v) => (v == null ? "—" : `${Math.round(v * 100)}%`);
