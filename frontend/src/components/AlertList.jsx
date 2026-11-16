import { Link } from "react-router-dom";
import { api } from "../api.js";
import { LevelBadge, pct } from "./ui.jsx";

export default function AlertList({ alerts, onChange, compact = false }) {
  if (!alerts.length) return <div className="state">No alerts.</div>;
  const ack = async (id) => {
    await api.ack(id);
    onChange?.();
  };
  return (
    <table className="table">
      <thead>
        <tr>
          {!compact && <th>Engine</th>}
          <th className="num">Cycle</th><th>Level</th><th>Type</th>
          <th className="num">Confidence</th><th>Details</th><th />
        </tr>
      </thead>
      <tbody>
        {alerts.map((a) => (
          <tr key={a.id} className={a.acknowledged ? "dim" : ""}>
            {!compact && <td><Link className="mono" to={`/engines/${a.engine_id}`}>{a.engine_serial}</Link></td>}
            <td className="num mono">{a.cycle}</td>
            <td><LevelBadge level={a.level} /></td>
            <td><span className="tag">{a.kind === "RUL" ? "RUL forecast" : "Anomaly"}</span></td>
            <td className="num mono">{pct(a.confidence)}</td>
            <td className="msg">{a.message}</td>
            <td className="num">
              {a.acknowledged ? <span className="muted small">acknowledged</span> :
                <button className="btn" onClick={() => ack(a.id)}>Acknowledge</button>}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
