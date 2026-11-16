"""Train and evaluate the AeroHealth model stack on a C-MAPSS sub-dataset.

Served RUL model = weighted average of
  * a deep ensemble of LSTMs (temporal patterns, differentiable -> SHAP per cycle),
  * a gradient-boosting model on window statistics (robust, strong on small data),
with split-conformal 90 % intervals calibrated on engines never seen in training.

Engines are split 70 / 15 / 15:
  train -> fit the models
  val   -> early stopping and ensemble weight
  calib -> conformal calibration (kept untouched so coverage is honest)

Usage:
    python -m aerohealth.ml.train --dataset FD001                 # full artifacts for the API
    python -m aerohealth.ml.train --dataset FD004 --metrics-only  # benchmark only
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch
from sklearn.ensemble import HistGradientBoostingRegressor

from aerohealth import config
from aerohealth.ml import data as D
from aerohealth.ml.conformal import BinnedConformal
from aerohealth.ml.features import window_features
from aerohealth.ml.health import HEALTHY_FRACTION, HealthModel
from aerohealth.ml.metrics import coverage, nasa_score, rmse
from aerohealth.ml.nets import predict_members, train_model

torch.set_num_threads(max(torch.get_num_threads(), 1))


def make_gbm() -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05, random_state=config.SEED)


def detection_report(health: HealthModel, df: pd.DataFrame) -> dict:
    """Lead time of the first persistent anomaly and false-alarm rate on held-out engines."""
    lead, false_alarm_cycles, healthy_cycles = [], 0, 0
    for _, g in df.groupby("unit"):
        res = health.analyse_unit(g)
        life = g["cycle"].max()
        healthy = g["cycle"].to_numpy() <= HEALTHY_FRACTION * life
        false_alarm_cycles += int(res["is_anomaly"].to_numpy()[healthy].sum())
        healthy_cycles += int(healthy.sum())
        hits = res.loc[res["is_anomaly"] & ~healthy, "cycle"]
        if len(hits):
            lead.append(int(life - hits.iloc[0]))
    return {
        "engines_detected_pct": round(100 * len(lead) / df["unit"].nunique(), 1),
        "median_lead_time_cycles": float(np.median(lead)) if lead else None,
        "false_alarm_rate_pct": round(100 * false_alarm_cycles / max(healthy_cycles, 1), 2),
    }


def scores(y, pred, lo=None, hi=None) -> dict:
    out = {"rmse": round(rmse(y, pred), 2), "nasa_score": round(nasa_score(y, pred), 1)}
    if lo is not None:
        out["interval_coverage_pct"] = round(100 * coverage(y, lo, hi), 1)
        out["mean_interval_width"] = round(float(np.mean(hi - lo)), 1)
    return out


def main(dataset: str, epochs: int, out_dir: Path, metrics_only: bool = False,
         n_seeds: int = config.N_SEEDS) -> dict:
    rng = np.random.default_rng(config.SEED)
    train = D.add_train_rul(D.load_raw(dataset, "train"))
    test = D.add_test_rul(D.load_raw(dataset, "test"), D.load_test_rul(dataset))

    pre = D.Preprocessor(n_conditions=config.DATASET_INFO[dataset]["conditions"]).fit(train)
    inputs = pre.model_inputs
    print(f"[{dataset}] inputs ({len(inputs)}): {inputs}")
    train_n, test_n = pre.transform(train), pre.transform(test)

    units = rng.permutation(train_n["unit"].unique())
    n = len(units)
    val_u, cal_u = units[: int(0.15 * n)], units[int(0.15 * n): int(0.30 * n)]
    tr = train_n[~train_n["unit"].isin(np.concatenate([val_u, cal_u]))]
    va = train_n[train_n["unit"].isin(val_u)]
    ca = train_n[train_n["unit"].isin(cal_u)]

    W = config.WINDOW
    Xtr, ytr, _ = D.make_windows(tr, inputs, W)
    Xva, yva, _ = D.make_windows(va, inputs, W)
    Xca, yca, _ = D.make_windows(ca, inputs, W)
    Xte, yte_raw, _ = D.make_windows(test_n, inputs, W, cap=None, last_only=True)
    yte = np.minimum(yte_raw, config.RUL_CAP)
    print(f"windows train {Xtr.shape}  val {Xva.shape}  calib {Xca.shape}  test {Xte.shape}")

    # --- members --------------------------------------------------------------
    lstms, histories = [], []
    for seed in range(n_seeds):
        print(f"LSTM seed {seed}")
        m, h = train_model(Xtr, ytr, Xva, yva, epochs=epochs, seed=config.SEED + seed, verbose=False)
        print(f"  {len(h)} epochs, best val RMSE {min(e['val_rmse'] for e in h):.2f}")
        lstms.append(m)
        histories.append(h)
    gbm = make_gbm().fit(window_features(Xtr), ytr)

    def member_preds(X):
        return predict_members(lstms, X).mean(0), np.clip(gbm.predict(window_features(X)), 0, None)

    # --- ensemble weight on validation engines ------------------------------------
    l_va, g_va = member_preds(Xva)
    grid = np.round(np.linspace(0, 1, 11), 2)
    val_rmse = {float(w): rmse(yva, w * l_va + (1 - w) * g_va) for w in grid}
    w = min(val_rmse, key=val_rmse.get)
    print(f"ensemble weight on LSTM = {w}  (val RMSE {val_rmse[w]:.2f})")

    # --- conformal calibration on untouched engines -----------------------------
    l_ca, g_ca = member_preds(Xca)
    conformal = BinnedConformal(level=config.INTERVAL_LEVEL).fit(w * l_ca + (1 - w) * g_ca, yca)

    # --- test evaluation (official protocol: last cycle of each test engine) ----
    l_te, g_te = member_preds(Xte)
    e_te = w * l_te + (1 - w) * g_te
    lo, hi = conformal.interval(e_te)
    single = predict_members(lstms[:1], Xte)[0]

    health = HealthModel(pre.features).fit(tr)
    metrics = {
        "dataset": dataset,
        "n_test_engines": int(len(yte)),
        "window": W,
        "ensemble_weight_lstm": w,
        "ensemble": scores(yte, e_te, lo, hi),
        "lstm_ensemble": scores(yte, l_te),
        "lstm_single": scores(yte, single),
        "gbm": scores(yte, g_te),
        "anomaly_detection": detection_report(health, pd.concat([va, ca])),
        "interval_level_pct": int(100 * config.INTERVAL_LEVEL),
    }
    print(json.dumps(metrics, indent=2))

    out_dir.mkdir(parents=True, exist_ok=True)
    if metrics_only:
        (out_dir / f"{dataset}.json").write_text(json.dumps(metrics, indent=2))
        return metrics

    version = f"{dataset.lower()}-ens-{datetime.now(timezone.utc):%Y%m%d%H%M}"
    for i, m in enumerate(lstms):
        torch.save({"config": m.config, "state_dict": m.state_dict()}, out_dir / f"lstm_{i}.pt")
    joblib.dump(gbm, out_dir / "gbm.joblib")
    joblib.dump(conformal, out_dir / "conformal.joblib")
    joblib.dump(pre, out_dir / "preprocessor.joblib")
    joblib.dump(health, out_dir / "health.joblib")
    np.save(out_dir / "shap_background.npy", Xtr[rng.choice(len(Xtr), size=100, replace=False)])
    meta = {
        "model_version": version, "dataset": dataset, "sensors": pre.features, "inputs": inputs,
        "window": W, "rul_cap": config.RUL_CAP, "n_lstm": len(lstms), "weight_lstm": w,
        "trained_at": datetime.now(timezone.utc).isoformat(), "metrics": metrics,
        "history": histories[0], "val_rmse_by_weight": val_rmse,
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    for old in ("lstm.pt",):  # artifacts of the previous single-LSTM version
        (out_dir / old).unlink(missing_ok=True)
    print(f"artifacts saved to {out_dir}")
    return metrics


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", default=config.DEFAULT_DATASET, choices=list(config.DATASET_INFO))
    p.add_argument("--epochs", type=int, default=120)
    p.add_argument("--seeds", type=int, default=config.N_SEEDS)
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--metrics-only", action="store_true")
    a = p.parse_args()
    out = a.out or (config.ARTIFACTS_DIR / "benchmarks" if a.metrics_only else config.ARTIFACTS_DIR)
    main(a.dataset, a.epochs, out, a.metrics_only, a.seeds)
