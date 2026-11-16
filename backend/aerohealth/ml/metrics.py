"""Evaluation metrics used in the PHM 2008 / C-MAPSS literature."""
from __future__ import annotations

import numpy as np


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((np.asarray(y_true) - np.asarray(y_pred)) ** 2)))


def nasa_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Asymmetric PHM08 score: late predictions (over-estimating RUL) cost more."""
    d = np.asarray(y_pred) - np.asarray(y_true)
    return float(np.sum(np.where(d < 0, np.exp(-d / 13) - 1, np.exp(d / 10) - 1)))


def coverage(y_true, lower, upper) -> float:
    y = np.asarray(y_true)
    return float(np.mean((y >= lower) & (y <= upper)))
