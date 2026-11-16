"""Hand-crafted window features for the gradient-boosting member of the ensemble."""
from __future__ import annotations

import numpy as np

STATS = ["last", "mean", "std", "slope"]


def window_features(X: np.ndarray) -> np.ndarray:
    """(n, T, F) windows -> (n, 4F): last value, mean, std and linear slope per input."""
    t = np.arange(X.shape[1]) - (X.shape[1] - 1) / 2
    slope = (X * t[None, :, None]).sum(1) / (t ** 2).sum()
    return np.hstack([X[:, -1], X.mean(1), X.std(1), slope])


def feature_names(inputs: list[str]) -> list[str]:
    return [f"{inp}_{stat}" for stat in STATS for inp in inputs]
