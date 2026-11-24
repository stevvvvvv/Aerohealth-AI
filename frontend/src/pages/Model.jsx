import { api } from "../api.js";
import { useFetch } from "../useFetch.js";
import Plot from "../components/Plot.jsx";
import { Card, Loading, Stat } from "../components/ui.jsx";
import { C, baseLayout } from "../theme.js";

const CONDITIONS = { FD001: "1 condition · HPC fault", FD002: "6 conditions · HPC fault", FD003: "1 condition · HPC + fan", FD004: "6 conditions · HPC + fan" };

export default function Model() {
  const { data, error, loading } = useFetch(api.model);
  if (loading || error) return <Loading error={error} />;
  const m = data.metrics;
  const h = data.history;
  const rows = [
    ["Ensemble — 3 LSTMs + GBM", "served", m.ensemble, `Conformal ${m.interval_level_pct}%`, "SHAP per input × cycle"],
    [`LSTM deep ensemble (×${data.n_lstm})`, "", m.lstm_ensemble, "—", "SHAP (expected gradients)"],
    ["Single LSTM", "", m.lstm_single, "—", "SHAP (expected gradients)"],
    ["Gradient boosting on window features", "baseline", m.gbm, "—", "TreeSHAP"],
  ];
  const bench = Object.entries(data.benchmarks || {});
  const f2 = (v) => Number(v).toFixed(2);
  return (
    <>
      <header className="page-head">
        <div>
          <h1>Model card</h1>
          <p className="muted mono">{data.model_version} · trained {new Date(data.trained_at).toLocaleString()}</p>
        </div>
      </header>

      <div className="readouts">
        <Stat label="Ensemble RMSE" value={f2(m.ensemble.rmse)} sub={`cycles · baseline GBM ${f2(m.gbm.rmse)}`} />
        <Stat label="PHM08 score" value={m.ensemble.nasa_score} sub={`baseline ${m.gbm.nasa_score} · lower is better`} />
        <Stat label="Interval coverage" value={`${m.ensemble.interval_coverage_pct}%`} sub={`target ${m.interval_level_pct}% · width ${m.ensemble.mean_interval_width} cyc`} />
        <Stat label="Anomaly lead time" value={`${m.anomaly_detection.median_lead_time_cycles} cyc`} sub={`median before failure · ${m.anomaly_detection.false_alarm_rate_pct}% false alarms`} />
      </div>

      <div className="grid-2">
        <Card title={`Benchmark on the official ${data.dataset} test set`} subtitle={`RUL capped at ${data.rul_cap} cycles, last cycle of each of the ${m.n_test_engines} test engines`}>
          <table className="table">
            <thead><tr><th>Model</th><th className="num">RMSE</th><th className="num">PHM08 score</th><th>Uncertainty</th><th>Explainability</th></tr></thead>
            <tbody>
              {rows.map(([name, tag, s, unc, xai]) => (
                <tr key={name}>
                  <td className={tag === "served" ? "strong" : ""}>{name} {tag && <span className="tag">{tag}</span>}</td>
                  <td className="num mono">{f2(s.rmse)}</td><td className="num mono">{s.nasa_score}</td>
                  <td className={unc === "—" ? "muted" : ""}>{unc}</td><td>{xai}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="small muted" style={{ marginTop: 12 }}>
            Ensemble weight on the LSTMs = {data.weight_lstm}, chosen on validation engines. Intervals are calibrated on a third
            set of engines never used for training or model selection.
          </p>
        </Card>
        <Card title="Learning curve" subtitle="LSTM #1 — RMSE per epoch, early stopping on validation engines">
          <Plot
            height={280}
            data={[
              { x: h.map((e) => e.epoch), y: h.map((e) => e.train_rmse), name: "Train (with dropout)", mode: "lines", line: { color: C.series[0], width: 2 } },
              { x: h.map((e) => e.epoch), y: h.map((e) => e.val_rmse), name: "Validation", mode: "lines", line: { color: C.series[1], width: 2 } },
            ]}
            layout={baseLayout({ hovermode: "x unified", xaxis: { title: { text: "Epoch" } },
              yaxis: { title: { text: "RMSE (cycles)" }, range: [0, 40] } })}
          />
        </Card>
      </div>

      {bench.length > 1 && (
        <Card title="Generalisation across the four C-MAPSS subsets" subtitle="Same pipeline, retrained per subset — RMSE on each official test set (lower is better)">
          <table className="table">
            <thead>
              <tr><th>Subset</th><th>Setting</th><th className="num">Test engines</th><th className="num">Ensemble</th>
                <th className="num">LSTM ×{data.n_lstm}</th><th className="num">GBM baseline</th><th className="num">Coverage (90% target)</th><th className="num">PHM08 score</th></tr>
            </thead>
            <tbody>
              {bench.map(([ds, b]) => (
                <tr key={ds}>
                  <td className="strong mono">{ds}</td><td>{CONDITIONS[ds]}</td>
                  <td className="num mono">{b.n_test_engines}</td>
                  <td className="num mono strong">{f2(b.ensemble.rmse)}</td>
                  <td className="num mono">{f2(b.lstm_ensemble.rmse)}</td>
                  <td className="num mono">{f2(b.gbm.rmse)}</td>
                  <td className="num mono">{b.ensemble.interval_coverage_pct}%</td>
                  <td className="num mono">{b.ensemble.nasa_score}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      <div className="grid-2">
        <Card title="Model inputs" subtitle={`${data.features.length} inputs, window of ${data.window} cycles`}>
          <table className="table">
            <thead><tr><th>Channel</th><th>Symbol</th><th>Measurement</th><th>Unit</th></tr></thead>
            <tbody>
              {data.features.map((f) => (
                <tr key={f.sensor}><td className="mono">{f.sensor}</td><td className="strong">{f.name}</td><td>{f.description}</td><td className="muted">{f.unit}</td></tr>
              ))}
            </tbody>
          </table>
        </Card>
        <Card title="Alerting policy">
          <ul className="policy">
            <li><b>Critical</b> when P(RUL ≤ {data.thresholds.critical_rul} cycles) ≥ {data.thresholds.alert_probability * 100}%</li>
            <li><b>Warning</b> when P(RUL ≤ {data.thresholds.warning_rul} cycles) ≥ {data.thresholds.alert_probability * 100}%</li>
            <li>Probabilities come from the conformal residual distribution of engines with a similar predicted RUL</li>
            <li><b>Anomaly</b> after {data.thresholds.anomaly_persistence} consecutive cycles above the 99th percentile of the healthy baseline</li>
            <li>Alerts fire on state transitions only, with hysteresis, to limit alert fatigue</li>
          </ul>
        </Card>
      </div>
    </>
  );
}
