"""Split-conformal prediction intervals, conditioned on the predicted RUL.

Errors are much larger far from failure than close to it, so a single
global interval would be too wide at the end of life (where it matters)
and too narrow early on. Calibration residuals are therefore grouped by
predicted-RUL bin ("Mondrian" conformal prediction). Each bin keeps its
empirical residual distribution, which also gives a non-parametric
probability P(RUL <= threshold).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

DEFAULT_EDGES = (0, 15, 30, 50, 75, 100, np.inf)


@dataclass
class BinnedConformal:
    level: float = 0.90
    edges: tuple = DEFAULT_EDGES
    residuals: list[np.ndarray] = field(default_factory=list)   # y - prediction, per bin

    def _bin(self, pred: np.ndarray) -> np.ndarray:
        return np.clip(np.digitize(pred, self.edges[1:-1]), 0, len(self.edges) - 2)

    def fit(self, pred: np.ndarray, y: np.ndarray) -> "BinnedConformal":
        b = self._bin(pred)
        self.residuals = [np.sort(y[b == i] - pred[b == i]) for i in range(len(self.edges) - 1)]
        for i, r in enumerate(self.residuals):  # merge tiny bins into their neighbour
            if len(r) < 30:
                self.residuals[i] = self.residuals[i - 1] if i else self.residuals[i + 1]
        return self

    def interval(self, pred: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        a = (1 - self.level) / 2
        lo, hi = np.empty_like(pred, dtype=float), np.empty_like(pred, dtype=float)
        for i, b in enumerate(self._bin(pred)):
            r = self.residuals[b]
            n = len(r)
            # finite-sample corrected quantiles
            lo[i] = pred[i] + r[max(int(np.floor(a * (n + 1))) - 1, 0)]
            hi[i] = pred[i] + r[min(int(np.ceil((1 - a) * (n + 1))) - 1, n - 1)]
        return np.clip(lo, 0, None), hi

    def prob_below(self, pred: np.ndarray, threshold: float) -> np.ndarray:
        """P(true RUL <= threshold) from the bin's empirical residuals."""
        out = np.empty_like(pred, dtype=float)
        for i, b in enumerate(self._bin(pred)):
            r = self.residuals[b]
            out[i] = np.searchsorted(r, threshold - pred[i], side="right") / len(r)
        return out
