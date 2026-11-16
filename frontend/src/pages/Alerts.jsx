import { useState } from "react";
import { api } from "../api.js";
import { useFetch } from "../useFetch.js";
import AlertList from "../components/AlertList.jsx";
import { Card, Loading } from "../components/ui.jsx";

export default function Alerts() {
  const [level, setLevel] = useState("");
  const [kind, setKind] = useState("");
  const [openOnly, setOpenOnly] = useState(true);
  const { data, error, loading, reload } = useFetch(
    () => api.alerts({ level, kind, open_only: openOnly, limit: 500 }), [level, kind, openOnly]);

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Alerts</h1>
          <p className="muted">RUL forecasts and anomaly detections, with confidence level</p>
        </div>
      </header>
      <Card
        title={data ? `${data.length} alerts` : "Alerts"}
        actions={
          <div className="filters">
            <select value={level} onChange={(e) => setLevel(e.target.value)}>
              <option value="">All levels</option>
              <option value="CRITICAL">Critical</option>
              <option value="WARNING">Warning</option>
            </select>
            <select value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="">All types</option>
              <option value="RUL">RUL forecast</option>
              <option value="ANOMALY">Anomaly</option>
            </select>
            <label className="check">
              <input type="checkbox" checked={openOnly} onChange={(e) => setOpenOnly(e.target.checked)} /> Open only
            </label>
          </div>
        }
      >
        {loading || error ? <Loading error={error} /> : <AlertList alerts={data} onChange={reload} />}
      </Card>
    </>
  );
}
