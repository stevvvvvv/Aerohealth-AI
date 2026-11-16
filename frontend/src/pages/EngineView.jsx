import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api.js";
import { useFetch } from "../useFetch.js";
import Plot from "../components/Plot.jsx";
import { Card, Loading, Stat, StatusBadge, fmt, pct } from "../components/ui.jsx";
import AlertList from "../components/AlertList.jsx";
import { C, STATUS, baseLayout } from "../theme.js";

/** Contiguous runs of anomalous cycles -> shaded rectangles. */
function anomalyShapes(preds, yref = "paper") {
  const shapes = [];
  let start = null;
  preds.forEach((p, i) => {
    if (p.is_anomaly && start == null) start = p.cycle;
    const end = !p.is_anomaly || i === preds.length - 1;
    if (start != null && end) {
      shapes.push({
        type: "rect", xref: "x", yref, x0: start - 0.5, x1: (p.is_anomaly ? p.cycle : preds[i - 1].cycle) + 0.5,
        y0: 0, y1: 1, fillcolor: "rgba(250,178,25,0.10)", line: { width: 0 }, layer: "below",
      });
      start = null;
    }
  });
  return shapes;
}

export default function EngineView() {
  const { id } = useParams();
  const engine = useFetch(() => api.engine(id), [id]);
  const preds = useFetch(() => api.predictions(id), [id]);
  const sensorMeta = useFetch(api.sensors);
  const [selected, setSelected] = useState(["s4", "s11", "s12"]);
  const [cycle, setCycle] = useState(null);
  const series = useFetch(() => api.sensorSeries(id, selected), [id, selected.join(",")]);
  const explain = useFetch(() => api.explain(id, cycle), [id, cycle]);
  const alerts = useFetch(() => api.alerts({ engine_id: id }), [id]);

  useEffect(() => setCycle(null), [id]);

  const meta = useMemo(
    () => Object.fromEntries((sensorMeta.data || []).map((s) => [s.sensor, s])), [sensorMeta.data]);

  if (engine.loading || preds.loading || engine.error || preds.error)
    return <Loading error={engine.error || preds.error} />;

  const e = engine.data;
  const P = preds.data;
  const L = e.latest;
  const x = P.map((p) => p.cycle);
  const hasTruth = P.some((p) => p.true_rul != null);
  const shapes = anomalyShapes(P);
  const usedSensors = (sensorMeta.data || []).filter((s) => s.used_by_model);

  const toggle = (s) =>
    setSelected((cur) => (cur.includes(s) ? cur.filter((c) => c !== s) : cur.length >= 3 ? [...cur.slice(1), s] : [...cur, s]));

  return (
    <>
      <header className="page-head">
        <div>
          <p className="crumbs"><Link to="/">Fleet</Link> / {e.serial}</p>
          <h1 className="mono">{e.serial} <StatusBadge status={e.status} /></h1>
          <p className="muted">C-MAPSS {e.dataset} · unit {e.id} · {e.last_cycle} flight cycles recorded</p>
        </div>
      </header>

      <div className="stats">
        <Stat label="Predicted RUL" value={`${fmt(L.rul_mean)} cyc`} sub={`90% interval ${fmt(L.rul_lower)}–${fmt(L.rul_upper)}`} />
        <Stat label="P(RUL ≤ 20 cycles)" value={pct(L.p_critical)} sub="critical threshold" accent={L.p_critical >= 0.5 ? STATUS.CRITICAL.color : undefined} />
        <Stat label="Health index" value={pct(L.health_index)} sub={L.is_anomaly ? "anomalous behaviour" : "within healthy envelope"} />
        {hasTruth && <Stat label="True RUL" value={`${L.true_rul} cyc`} sub="NASA ground truth (demo only)" />}
      </div>

      <Card title="Remaining useful life" subtitle="LSTM estimate with Monte-Carlo dropout 90% interval (calibrated). Click the chart to explain a given cycle.">
        <Plot
          height={340}
          data={[
            { x, y: P.map((p) => p.rul_upper), mode: "lines", line: { width: 0 }, hoverinfo: "skip", showlegend: false },
            { x, y: P.map((p) => p.rul_lower), mode: "lines", line: { width: 0 }, fill: "tonexty",
              fillcolor: "rgba(57,135,229,0.18)", name: "90% interval", hoverinfo: "skip" },
            { x, y: P.map((p) => p.rul_mean), mode: "lines", name: "Predicted RUL", line: { color: C.series[0], width: 2 },
              customdata: P.map((p) => [p.rul_lower, p.rul_upper, p.p_critical]),
              hovertemplate: "Cycle %{x}<br>RUL %{y:.0f} [%{customdata[0]:.0f}–%{customdata[1]:.0f}]<br>P(≤20) %{customdata[2]:.0%}<extra></extra>" },
            ...(hasTruth ? [{ x, y: P.map((p) => Math.min(p.true_rul, 125)), mode: "lines", name: "True RUL (capped 125)",
              line: { color: C.series[1], width: 2, dash: "dash" }, hovertemplate: "True RUL %{y}<extra></extra>" }] : []),
          ]}
          layout={baseLayout({
            hovermode: "x unified",
            xaxis: { title: { text: "Flight cycle" } },
            yaxis: { title: { text: "Cycles remaining" }, rangemode: "tozero" },
            shapes: [
              ...[20, 50].map((y) => ({ type: "line", xref: "paper", x0: 0, x1: 1, y0: y, y1: y,
                line: { color: y === 20 ? STATUS.CRITICAL.color : STATUS.WARNING.color, width: 1, dash: "dot" } })),
              ...(cycle ? [{ type: "line", x0: cycle, x1: cycle, yref: "paper", y0: 0, y1: 1, line: { color: C.text2, width: 1 } }] : []),
            ],
            annotations: [20, 50].map((y) => ({ xref: "paper", x: 1, y, text: y === 20 ? "critical" : "warning",
              showarrow: false, xanchor: "right", yanchor: "bottom", font: { size: 11, color: C.muted } })),
          })}
          onClick={(ev) => setCycle(ev.points[0].x)}
        />
      </Card>

      <div className="grid-2">
        <Card title="Health index" subtitle="Isolation Forest vs. healthy baseline · shaded = persistent anomaly">
          <Plot
            height={260}
            data={[{ x, y: P.map((p) => p.health_index), mode: "lines", line: { color: C.series[0], width: 2 },
              customdata: P.map((p) => [p.anomaly_confidence, p.top_deviation.map((s) => meta[s]?.name || s).join(", ")]),
              hovertemplate: "Cycle %{x}<br>Health %{y:.0%}<br>Exceeds %{customdata[0]:.1%} of healthy baseline<br>Top deviations: %{customdata[1]}<extra></extra>" }]}
            layout={baseLayout({ shapes, xaxis: { title: { text: "Flight cycle" } },
              yaxis: { tickformat: ".0%", range: [-0.03, 1.05] } })}
          />
        </Card>
        <Card title="Anomaly score" subtitle={`Alert threshold = 99th percentile of healthy data (${e.anomaly_threshold.toFixed(3)})`}>
          <Plot
            height={260}
            data={[{ x, y: P.map((p) => p.anomaly_score), mode: "lines", line: { color: C.series[0], width: 2 },
              hovertemplate: "Cycle %{x}<br>Score %{y:.3f}<extra></extra>" }]}
            layout={baseLayout({
              shapes: [...shapes, { type: "line", xref: "paper", x0: 0, x1: 1, y0: e.anomaly_threshold, y1: e.anomaly_threshold,
                line: { color: STATUS.WATCH.color, width: 1, dash: "dot" } }],
              xaxis: { title: { text: "Flight cycle" } },
            })}
          />
        </Card>
      </div>

      <Card
        title="Sensor explorer"
        subtitle="Raw measurements — pick up to 3 sensors. Shaded = anomalous cycles."
        actions={
          <div className="chips">
            {usedSensors.map((s) => (
              <button key={s.sensor} className={selected.includes(s.sensor) ? "chip on" : "chip"} onClick={() => toggle(s.sensor)}
                      title={`${s.description} (${s.unit})`}>
                {s.name}
              </button>
            ))}
          </div>
        }
      >
        {series.data && (
          <div className="multiples">
            {selected.map((s, i) => (
              <div key={s}>
                <div className="multiple-title">
                  <span className="dot" style={{ background: C.series[i] }} />
                  <strong>{meta[s]?.name}</strong> <span className="muted">{meta[s]?.description} ({meta[s]?.unit})</span>
                </div>
                <Plot
                  height={190}
                  data={[{ x: series.data.cycles, y: series.data.series[s], mode: "lines",
                    line: { color: C.series[i], width: 1.5 },
                    hovertemplate: `Cycle %{x}<br>${meta[s]?.name} %{y:.2f} ${meta[s]?.unit}<extra></extra>` }]}
                  layout={baseLayout({ shapes, margin: { l: 60, r: 12, t: 4, b: 28 } })}
                />
              </div>
            ))}
          </div>
        )}
      </Card>

      <div className="grid-2">
        <Card title={`Why this prediction? — cycle ${explain.data?.cycle ?? "…"}`}
              subtitle="SHAP (expected gradients) on the LSTM, summed over the 30-cycle window. Red lowers the predicted RUL, blue raises it.">
          {explain.loading || explain.error ? <Loading error={explain.error} /> : (
            <>
              <p className="small muted">
                Baseline (average prediction) <b className="mono">{explain.data.base_value.toFixed(0)}</b> cycles →
                prediction <b className="mono">{explain.data.prediction.toFixed(0)}</b> cycles
              </p>
              <Plot
                height={380}
                data={[{
                  type: "bar", orientation: "h",
                  y: [...explain.data.features].reverse().map((f) => `${f.name} · ${f.description}`),
                  x: [...explain.data.features].reverse().map((f) => f.shap_value),
                  marker: { color: [...explain.data.features].reverse().map((f) => (f.shap_value < 0 ? C.neg : C.pos)) },
                  hovertemplate: "%{y}<br>Contribution %{x:+.1f} cycles<extra></extra>",
                }]}
                layout={baseLayout({ margin: { l: 230, r: 16, t: 4, b: 36 }, bargap: 0.3,
                  xaxis: { title: { text: "Contribution to RUL (cycles)" }, zeroline: true, zerolinecolor: C.axis },
                  yaxis: { gridcolor: "rgba(0,0,0,0)", tickfont: { size: 11 } } })}
              />
            </>
          )}
        </Card>
        <Card title="Attribution over the input window" subtitle="Which sensors at which past cycles drove the estimate">
          {explain.data && (
            <Plot
              height={420}
              data={[{
                type: "heatmap", z: explain.data.heatmap,
                x: explain.data.window_cycles,
                y: explain.data.heatmap_sensors.map((s) => meta[s]?.name || s),
                colorscale: [[0, C.neg], [0.5, C.mid], [1, C.pos]], zmid: 0,
                colorbar: { title: { text: "cycles", side: "right" }, thickness: 10, outlinewidth: 0, tickfont: { color: C.text2 } },
                hovertemplate: "%{y} @ cycle %{x}<br>%{z:+.2f}<extra></extra>",
              }]}
              layout={baseLayout({ margin: { l: 70, r: 10, t: 4, b: 40 },
                xaxis: { title: { text: "Flight cycle" }, gridcolor: "rgba(0,0,0,0)" },
                yaxis: { gridcolor: "rgba(0,0,0,0)" } })}
            />
          )}
        </Card>
      </div>

      <Card title="Alert history" subtitle="Raised on state transitions (with hysteresis) to avoid alert fatigue">
        {alerts.data ? <AlertList alerts={alerts.data} onChange={alerts.reload} compact /> : <Loading error={alerts.error} />}
      </Card>
    </>
  );
}
