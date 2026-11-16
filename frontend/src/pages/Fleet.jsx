import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { useFetch } from "../useFetch.js";
import Plot from "../components/Plot.jsx";
import { Card, HealthBar, Loading, Stat, StatusBadge, fmt } from "../components/ui.jsx";
import { C, STATUS, baseLayout } from "../theme.js";

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
  const atRisk = [...data.engines].sort((a, b) => a.rul_mean - b.rul_mean).slice(0, 15).reverse();
  const m = model.data?.metrics?.ensemble;

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Fleet health</h1>
          <p className="muted">{data.engines.length} engines monitored · model {data.model_version}</p>
        </div>
      </header>

      <div className="stats">
        {ORDER.map((s) => (
          <Stat key={s} label={<><span style={{ color: STATUS[s].color }}>{STATUS[s].icon}</span> {STATUS[s].label}</>}
                value={data.counts[s] || 0} sub="engines" />
        ))}
        <Stat label="Model RMSE (test)" value={m ? Number(m.rmse).toFixed(2) : "—"} sub={m ? `cycles · ${m.interval_coverage_pct}% interval coverage` : ""} />
      </div>

      <div className="grid-2">
        <Card title="Most at-risk engines" subtitle="Predicted remaining useful life, 90% interval. Click a bar to open the engine.">
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
              margin: { l: 80, r: 16, t: 8, b: 40 }, bargap: 0.35,
              xaxis: { title: { text: "Remaining useful life (cycles)" }, rangemode: "tozero" },
              yaxis: { gridcolor: "rgba(0,0,0,0)" },
              shapes: [20, 50].map((x) => ({ type: "line", x0: x, x1: x, yref: "paper", y0: 0, y1: 1,
                line: { color: C.axis, width: 1, dash: "dot" } })),
            })}
            onClick={(ev) => navigate(`/engines/${ev.points[0].customdata[3]}`)}
          />
        </Card>
        <Card title="Fleet state" subtitle="Predicted RUL vs. health index — each dot is an engine">
          <Plot
            height={420}
            data={ORDER.map((s) => {
              const pts = data.engines.filter((e) => e.status === s);
              return {
                type: "scatter", mode: "markers", name: STATUS[s].label,
                x: pts.map((e) => e.health_index), y: pts.map((e) => e.rul_mean),
                text: pts.map((e) => e.serial), customdata: pts.map((e) => e.id),
                marker: { size: 9, color: STATUS[s].color, line: { color: C.surface, width: 1.5 } },
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
        title="All engines"
        actions={
          <div className="filters">
            <input placeholder="Search serial…" value={query} onChange={(e) => setQuery(e.target.value)} />
            <div className="seg">
              {["ALL", ...ORDER].map((s) => (
                <button key={s} className={status === s ? "on" : ""} onClick={() => setStatus(s)}>
                  {s === "ALL" ? "All" : STATUS[s].label}
                </button>
              ))}
            </div>
          </div>
        }
      >
        <table className="table">
          <thead>
            <tr>
              <th>Engine</th><th>Status</th><th className="num">Cycles</th>
              <th className="num">RUL</th><th className="num">90% interval</th>
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
                <td className="num mono muted">{fmt(e.rul_lower)}–{fmt(e.rul_upper)}</td>
                <td><HealthBar value={e.health_index} /></td>
                <td className="num mono">{e.open_alerts || <span className="muted">0</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </>
  );
}
