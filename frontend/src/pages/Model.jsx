import { api } from "../api.js";
import { useFetch } from "../useFetch.js";
import Plot from "../components/Plot.jsx";
import { Card, Loading, Stat } from "../components/ui.jsx";
import { C, baseLayout } from "../theme.js";

export default function Model() {
  const { data, error, loading } = useFetch(api.model);
  if (loading || error) return <Loading error={error} />;
  const m = data.metrics;
  const h = data.history;
  return (
    <>
      <header className="page-head">
        <div>
          <h1>Model card</h1>
          <p className="muted mono">{data.model_version} · trained {new Date(data.trained_at).toLocaleString()}</p>
        </div>
      </header>

      <div className="stats">
        <Stat label="LSTM RMSE" value={m.lstm.rmse} sub={`cycles · ${m.n_test_engines} test engines`} />
        <Stat label="PHM08 score" value={m.lstm.nasa_score} sub="asymmetric, lower is better" />
        <Stat label="Interval coverage" value={`${m.lstm.interval_coverage_pct}%`} sub={`target ${m.interval_level_pct}% · width ${m.lstm.mean_interval_width} cyc`} />
        <Stat label="Anomaly lead time" value={`${m.anomaly_detection.median_lead_time_cycles} cyc`} sub={`median before failure · ${m.anomaly_detection.false_alarm_rate_pct}% false alarms`} />
      </div>

      <div className="grid-2">
        <Card title="Benchmark on the official test set" subtitle="RUL capped at 125 cycles, last cycle of each test engine">
          <table className="table">
            <thead><tr><th>Model</th><th className="num">RMSE</th><th className="num">PHM08 score</th><th>Uncertainty</th><th>Explainability</th></tr></thead>
            <tbody>
              <tr><td>LSTM + MC dropout <span className="tag">served</span></td><td className="num mono">{m.lstm.rmse}</td>
                <td className="num mono">{m.lstm.nasa_score}</td><td>Calibrated 90% interval</td><td>SHAP per sensor × cycle</td></tr>
              <tr><td>Gradient boosting (window features)</td><td className="num mono">{m.baseline_gbm.rmse}</td>
                <td className="num mono">{m.baseline_gbm.nasa_score}</td><td className="muted">point estimate</td><td className="muted">SHAP per feature</td></tr>
            </tbody>
          </table>
          <p className="small muted" style={{ marginTop: 12 }}>
            On FD001 the tree baseline is slightly more accurate. The LSTM is served because it provides calibrated
            uncertainty (needed for risk-based alerts) and temporal attributions. See README → Results.
          </p>
        </Card>
        <Card title="Learning curve" subtitle="RMSE per epoch — early stopping on validation engines">
          <Plot
            height={280}
            data={[
              { x: h.map((e) => e.epoch), y: h.map((e) => e.train_rmse), name: "Train (with dropout)", mode: "lines", line: { color: C.series[0], width: 2 } },
              { x: h.map((e) => e.epoch), y: h.map((e) => e.val_rmse), name: "Validation", mode: "lines", line: { color: C.series[1], width: 2 } },
            ]}
            layout={baseLayout({ hovermode: "x unified", xaxis: { title: { text: "Epoch" } },
              yaxis: { title: { text: "RMSE (cycles)" }, type: "log" } })}
          />
        </Card>
      </div>

      <div className="grid-2">
        <Card title="Input sensors" subtitle={`${data.features.length} informative channels kept, window of ${data.window} cycles`}>
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
            <li><b>Anomaly</b> after {data.thresholds.anomaly_persistence} consecutive cycles above the 99th percentile of the healthy baseline</li>
            <li>Alerts fire on state transitions only, with hysteresis, to limit alert fatigue</li>
            <li>Confidence = model probability (RUL) or share of healthy baseline exceeded (anomaly)</li>
          </ul>
        </Card>
      </div>
    </>
  );
}
