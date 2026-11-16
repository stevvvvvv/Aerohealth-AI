"""Unsupervised anomaly detection and Health Index.

An Isolation Forest is fitted on the *healthy* early-life portion of every
training engine. Its anomaly score is then:
  * thresholded (99th percentile of healthy data) to flag anomalous cycles,
  * rescaled between the healthy and end-of-life levels to give a Health
    Index in [0, 1] (1 = as new, 0 = failure level).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from aerohealth import config

SMOOTH = 5            # rolling window applied to sensors before scoring
HEALTHY_FRACTION = 0.3


def smooth_unit(df: pd.DataFrame, features: list[str]) -> np.ndarray:
    """Causal rolling mean per unit (only past cycles -> usable online)."""
    return (
        df.groupby("unit")[features]
        .transform(lambda s: s.rolling(SMOOTH, min_periods=1).mean())
        .to_numpy()
    )


@dataclass
class HealthModel:
    features: list[str]
    forest: IsolationForest | None = None
    threshold: float = 0.0
    healthy_level: float = 0.0
    failure_level: float = 1.0
    healthy_scores: np.ndarray | None = None
    baseline_mean: np.ndarray | None = None
    baseline_std: np.ndarray | None = None

    def fit(self, train_norm: pd.DataFrame) -> "HealthModel":
        life = train_norm.groupby("unit")["cycle"].transform("max")
        healthy = (train_norm["cycle"] <= HEALTHY_FRACTION * life).to_numpy()
        X = smooth_unit(train_norm, self.features)
        self.forest = IsolationForest(n_estimators=300, random_state=config.SEED)
        self.forest.fit(X[healthy])
        scores = self.score(X)
        self.healthy_scores = np.sort(scores[healthy])
        self.threshold = float(np.quantile(self.healthy_scores, 0.99))
        self.healthy_level = float(np.median(self.healthy_scores))
        self.failure_level = float(np.median(scores[train_norm["rul"].to_numpy() <= 10]))
        self.baseline_mean = X[healthy].mean(0)
        self.baseline_std = X[healthy].std(0) + 1e-9
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        """Higher = more anomalous."""
        return -self.forest.score_samples(X)

    def health_index(self, scores: np.ndarray) -> np.ndarray:
        hi = 1 - (scores - self.healthy_level) / (self.failure_level - self.healthy_level)
        return np.clip(hi, 0, 1)

    def confidence(self, scores: np.ndarray) -> np.ndarray:
        """Share of the healthy baseline that the current score exceeds."""
        return np.searchsorted(self.healthy_scores, scores) / len(self.healthy_scores)

    def deviations(self, X: np.ndarray) -> np.ndarray:
        """Per-sensor z-score against the healthy baseline."""
        return (X - self.baseline_mean) / self.baseline_std

    def analyse_unit(self, unit_df: pd.DataFrame) -> pd.DataFrame:
        """Score every cycle of a single (normalised) engine sequence."""
        X = smooth_unit(unit_df.assign(unit=0), self.features)
        s = self.score(X)
        above = s > self.threshold
        # persistent anomaly = N consecutive cycles above threshold
        run = np.zeros(len(s), dtype=int)
        for i, a in enumerate(above):
            run[i] = run[i - 1] + 1 if (a and i > 0) else int(a)
        dev = self.deviations(X)
        return pd.DataFrame({
            "cycle": unit_df["cycle"].to_numpy(),
            "anomaly_score": s,
            "health_index": self.health_index(s),
            "is_anomaly": run >= config.ANOMALY_PERSISTENCE,
            "anomaly_confidence": self.confidence(s),
            "top_deviation": [
                [self.features[j] for j in np.argsort(-np.abs(d))[:3]] for d in dev
            ],
        })
