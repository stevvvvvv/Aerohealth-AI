import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { useFetch } from "../useFetch.js";
import Plot from "../components/Plot.jsx";
import { Card, HealthBar, Loading, RangeBar, StatusBadge, fmt } from "../components/ui.jsx";
import { C, MONO, STATUS, baseLayout } from "../theme.js";

const ORDER = ["CRITICAL", "WARNING", "WATCH", "HEALTHY"];

export default function Fleet() {
  const { data, error, loading } = useFetch(api.fleet);
  const model = useFetch(api.model);
  const [status, setStatus] = useState("ALL");
  const [query, setQuery] = useState("");
  const navigate = useNavigate();

  const engines = useMemo(() => {
    if (!data) return [];
    return data.engines
      .filter((e) => status === "ALL" || e.status === status)
      .filter((e) => e.serial.toLowerCase().includes(query.toLowerCase()))
      .sort((a, b) => (a.rul_mean ?? 1e9) - (b.rul_mean ?? 1e9));
  }, [data, status, query]);

  if (loading || error) return <Loading error={error} />;
  const total = data.engines.length;
  const atRisk = [...data.engines].sort((a, b) => a.rul_mean - b.rul_mean).slice(0, 15).reverse();
  const m = model.data?.metrics?.ensemble;
  const toggle = (s) => setStatus((cur) => (cur === s ? "ALL" : s));

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Fleet health</h1>
          <p className="muted">
            {total} turbofan engines, ranked by predicted remaining useful life
            {m && <> · ensemble RMSE {Number(m.rmse).toFixed(2)} cycles on the NASA test set</>}
          </p>
        </div>
      </header>

      <section className="strip" aria-label="Fleet status">
        <h3>Engines by status</h3>
        <div className="strip-bar" role="img" aria-label={ORDER.map((s) => `${data.counts[s] || 0} ${STATUS[s].label}`).join(", ")}>
          {ORDER.map((s) => (
            <div key={s} style={{ flexGrow: data.counts[s] || 0, background: STATUS[s].color, opacity: status === "ALL" || status === s ? 1 : 0.25 }} />
          ))}
        </div>
        <div className="strip-legend">
          {ORDER.map((s) => (
            <button key={s} className={status === s ? "on" : ""} style={{ color: STATUS[s].color }} onClick={() => toggle(s)}
                    aria-pressed={status === s}>
              <span aria-hidden>{STATUS[s].icon}</span>
              <span className="n">{data.counts[s] || 0}</span>
              <span className="l">{STATUS[s].label}</span>
            </button>
          ))}
          <span className="muted small" style={{ alignSelf: "center" }}>Select a status to filter the engine list</span>
        </div>
      </section>

      <div className="grid-2">
        <Card title="Most at-risk engines" subtitle="Predicted RUL with 90% interval. Select a bar to open the engine.">
          <Plot
            height={420}
            data={[{
              type: "bar", orientation: "h",
              y: atRisk.map((e) => e.serial), x: atRisk.map((e) => e.rul_mean),
              marker: { color: atRisk.map((e) => STATUS[e.status].color), line: { width: 0 } },
              error_x: {
                type: "data", symmetric: false, color: C.text2, thickness: 1.2, width: 3,
                array: atRisk.map((e) => e.rul_upper - e.rul_mean),
                arrayminus: atRisk.map((e) => e.rul_mean - e.rul_lower),
              },
              customdata: atRisk.map((e) => [e.rul_lower, e.rul_upper, STATUS[e.status].label, e.id]),
              hovertemplate: "<b>%{y}</b><br>RUL %{x:.0f} cycles<br>90%% interval %{customdata[0]:.0f}–%{customdata[1]:.0f}<br>%{customdata[2]}<extra></extra>",
            }]}
            layout={baseLayout({
              margin: { l: 82, r: 16, t: 8, b: 40 }, bargap: 0.4,
              xaxis: { title: { text: "Remaining useful life (cycles)" }, rangemode: "tozero" },
              yaxis: { gridcolor: "rgba(0,0,0,0)", tickfont: { family: MONO } },
              shapes: [[20, STATUS.CRITICAL.color], [50, STATUS.WARNING.color]].map(([x, c]) => ({ type: "line", x0: x, x1: x, yref: "paper", y0: 0, y1: 1,
                line: { color: c, width: 1, dash: "dot" } })),
            })}
            onClick={(ev) => navigate(`/engines/${ev.points[0].customdata[3]}`)}
          />
        </Card>
        <Card title="Fleet state" subtitle="Predicted RUL against health index. Each point is an engine.">
          <Plot
            height={420}
            data={ORDER.map((s) => {
              const pts = data.engines.filter((e) => e.status === s);
              return {
                type: "scatter", mode: "markers", name: STATUS[s].label,
                x: pts.map((e) => e.health_index), y: pts.map((e) => e.rul_mean),
                text: pts.map((e) => e.serial), customdata: pts.map((e) => e.id),
                marker: { size: 9, color: STATUS[s].color, line: { color: C.surface, width: 2 } },
                hovertemplate: "<b>%{text}</b><br>Health index %{x:.0%}<br>RUL %{y:.0f} cycles<extra></extra>",
              };
            })}
            layout={baseLayout({
              xaxis: { title: { text: "Health index" }, tickformat: ".0%", range: [-0.05, 1.05] },
              yaxis: { title: { text: "Predicted RUL (cycles)" }, rangemode: "tozero" },
            })}
            onClick={(ev) => navigate(`/engines/${ev.points[0].customdata}`)}
          />
        </Card>
      </div>

      <Card
        title={status === "ALL" ? "All engines" : `${STATUS[status].label} engines`}
        subtitle={`${engines.length} shown`}
        actions={
          <div className="filters">
            <input placeholder="Search serial number" aria-label="Search serial number" value={query} onChange={(e) => setQuery(e.target.value)} />
            {status !== "ALL" && <button className="btn" onClick={() => setStatus("ALL")}>Show all</button>}
          </div>
        }
      >
        <div className="table-scroll">
          <table className="table">
            <thead>
              <tr>
                <th>Engine</th><th>Status</th><th className="num">Cycles</th>
                <th className="num">RUL</th><th>Interval (0–125 cycles)</th>
                <th>Health index</th><th className="num">Open alerts</th>
              </tr>
            </thead>
            <tbody>
              {engines.map((e) => (
                <tr key={e.id} onClick={() => navigate(`/engines/${e.id}`)}>
                  <td><Link to={`/engines/${e.id}`} className="mono">{e.serial}</Link></td>
                  <td><StatusBadge status={e.status} /></td>
                  <td className="num mono">{e.last_cycle}</td>
                  <td className="num mono strong">{fmt(e.rul_mean)}</td>
                  <td><RangeBar mean={e.rul_mean} lower={e.rul_lower} upper={e.rul_upper} status={e.status} /></td>
                  <td><HealthBar value={e.health_index} /></td>
                  <td className="num mono">{e.open_alerts || <span className="muted">0</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}
