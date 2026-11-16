"""Train the full AeroHealth model stack on a C-MAPSS sub-dataset.

Usage:
    python -m aerohealth.ml.train --dataset FD001
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
from aerohealth.ml.health import HEALTHY_FRACTION, HealthModel
from aerohealth.ml.lstm import predict, predict_mc, train_model
from aerohealth.ml.metrics import coverage, nasa_score, rmse
from aerohealth.ml.predictor import Z


def window_features(X: np.ndarray) -> np.ndarray:
    """Hand-crafted features for the gradient-boosting baseline."""
    t = np.arange(X.shape[1]) - (X.shape[1] - 1) / 2
    slope = (X * t[None, :, None]).sum(1) / (t ** 2).sum()
    return np.hstack([X[:, -1], X.mean(1), X.std(1), slope])


def detection_report(health: HealthModel, val_norm: pd.DataFrame) -> dict:
    """Lead time of the first persistent anomaly and false-alarm rate on val engines."""
    lead, false_alarm_cycles, healthy_cycles = [], 0, 0
    for _, g in val_norm.groupby("unit"):
        res = health.analyse_unit(g)
        life = g["cycle"].max()
        healthy = g["cycle"].to_numpy() <= HEALTHY_FRACTION * life
        false_alarm_cycles += int(res["is_anomaly"].to_numpy()[healthy].sum())
        healthy_cycles += int(healthy.sum())
        hits = res.loc[res["is_anomaly"] & ~healthy, "cycle"]
        if len(hits):
            lead.append(int(life - hits.iloc[0]))
    return {
        "engines_detected_pct": round(100 * len(lead) / val_norm["unit"].nunique(), 1),
        "median_lead_time_cycles": float(np.median(lead)) if lead else None,
        "false_alarm_rate_pct": round(100 * false_alarm_cycles / max(healthy_cycles, 1), 2),
    }



def main(dataset: str, epochs: int, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(config.SEED)

    train = D.add_train_rul(D.load_raw(dataset, "train"))
    test = D.add_test_rul(D.load_raw(dataset, "test"), D.load_test_rul(dataset))

    pre = D.Preprocessor(n_conditions=config.DATASET_INFO[dataset]["conditions"]).fit(train)
    feats = pre.features
    print(f"[{dataset}] {len(feats)} informative sensors: {feats}")
    train_n, test_n = pre.transform(train), pre.transform(test)

    units = train_n["unit"].unique()
    val_units = rng.choice(units, size=int(0.2 * len(units)), replace=False)
    tr = train_n[~train_n["unit"].isin(val_units)]
    va = train_n[train_n["unit"].isin(val_units)]

    Xtr, ytr, _ = D.make_windows(tr, feats, config.WINDOW)
    Xva, yva, _ = D.make_windows(va, feats, config.WINDOW)
    print(f"train windows {Xtr.shape}, val windows {Xva.shape}")

    model, history = train_model(Xtr, ytr, Xva, yva, epochs=epochs, seed=config.SEED)

    # --- uncertainty calibration (MC dropout scaled to nominal coverage) ---
    mu_v, sd_v = predict_mc(model, Xva, samples=config.MC_SAMPLES)
    ratio = np.abs(yva - mu_v) / np.maximum(sd_v, 1e-6)
    k = float(np.quantile(ratio, config.INTERVAL_LEVEL))
    print(f"calibration factor k = {k:.2f} (raw z = {Z:.2f})")

    # --- test evaluation: last cycle of every test engine (official protocol) ---
    Xte, yte_raw, _ = D.make_windows(test_n, feats, config.WINDOW, cap=None, last_only=True)
    yte = np.minimum(yte_raw, config.RUL_CAP)
    mu_t, sd_t = predict_mc(model, Xte, samples=config.MC_SAMPLES)
    det_t = predict(model, Xte)
    lo, hi = np.clip(mu_t - k * sd_t, 0, None), mu_t + k * sd_t

    # --- baseline for comparison ---
    gbm = HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05, random_state=config.SEED)
    gbm.fit(window_features(Xtr), ytr)
    gbm_pred = np.clip(gbm.predict(window_features(Xte)), 0, None)

    # --- health / anomaly model ---
    health = HealthModel(feats).fit(tr)
    detection = detection_report(health, va)

    metrics = {
        "dataset": dataset,
        "n_test_engines": int(len(yte)),
        "lstm": {
            "rmse": round(rmse(yte, det_t), 2),
            "rmse_mc_mean": round(rmse(yte, mu_t), 2),
            "nasa_score": round(nasa_score(yte, det_t), 1),
            "interval_coverage_pct": round(100 * coverage(yte, lo, hi), 1),
            "mean_interval_width": round(float(np.mean(hi - lo)), 1),
        },
        "baseline_gbm": {
            "rmse": round(rmse(yte, gbm_pred), 2),
            "nasa_score": round(nasa_score(yte, gbm_pred), 1),
        },
        "anomaly_detection": detection,
        "interval_level_pct": int(100 * config.INTERVAL_LEVEL),
        "epochs_trained": len(history),
    }
    print(json.dumps(metrics, indent=2))

    version = f"{dataset.lower()}-lstm-{datetime.now(timezone.utc):%Y%m%d%H%M}"
    torch.save({"config": model.config, "state_dict": model.state_dict()}, out_dir / "lstm.pt")
    joblib.dump(pre, out_dir / "preprocessor.joblib")
    joblib.dump(health, out_dir / "health.joblib")
    bg = Xtr[rng.choice(len(Xtr), size=100, replace=False)]
    np.save(out_dir / "shap_background.npy", bg)
    meta = {
        "model_version": version, "dataset": dataset, "features": feats,
        "window": config.WINDOW, "rul_cap": config.RUL_CAP, "calibration_k": k,
        "trained_at": datetime.now(timezone.utc).isoformat(), "metrics": metrics,
        "history": history,
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    print(f"artifacts saved to {out_dir}")
    return metrics


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", default=config.DEFAULT_DATASET, choices=list(config.DATASET_INFO))
    p.add_argument("--epochs", type=int, default=120)
    p.add_argument("--out", type=Path, default=config.ARTIFACTS_DIR)
    a = p.parse_args()
    main(a.dataset, a.epochs, a.out)
