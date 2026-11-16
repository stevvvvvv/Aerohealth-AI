"""SHAP explanations for the RUL ensemble.

The served prediction is ``w * mean(LSTMs) + (1 - w) * GBM``. SHAP values are
additive, so the explanation of the ensemble is the same weighted sum of the
members' explanations:
  * LSTM ensemble -> ``shap.GradientExplainer`` (expected gradients) on every
    (time step, input) cell of the window,
  * GBM           -> ``shap.TreeExplainer`` (exact) on the window statistics
    (last / mean / std / slope), summed back to the input they come from.
"""
from __future__ import annotations

import numpy as np
import shap
import torch

from aerohealth.ml.features import STATS, window_features
from aerohealth.ml.nets import Ensemble


class _Out2D(torch.nn.Module):
    def __init__(self, model):
        super().__init__()
        self.model = model

    def forward(self, x):
        return self.model(x).unsqueeze(-1)


class EnsembleExplainer:
    NSAMPLES = 100

    def __init__(self, lstms, gbm, w: float, background: np.ndarray, inputs: list[str]):
        self.inputs, self.w, self.gbm = inputs, w, gbm
        self.net = _Out2D(Ensemble(lstms)).eval()
        bg = torch.from_numpy(background.astype(np.float32))
        self.deep = shap.GradientExplainer(self.net, bg, batch_size=self.NSAMPLES)
        self.tree = shap.TreeExplainer(gbm)
        with torch.no_grad():
            base_lstm = float(self.net(bg).mean())
        base_gbm = float(np.ravel(self.tree.expected_value)[0])
        self.base_value = w * base_lstm + (1 - w) * base_gbm
        self.deep.shap_values(bg[:1], nsamples=self.NSAMPLES, rseed=0)  # warm-up: first pass at this batch size is slow

    def explain(self, window: np.ndarray) -> dict:
        T, F = window.shape
        x = torch.from_numpy(window[None].astype(np.float32))
        deep = np.asarray(self.deep.shap_values(x, nsamples=self.NSAMPLES, rseed=0)).reshape(T, F)
        tree = np.asarray(self.tree.shap_values(window_features(window[None]))).reshape(len(STATS), F)
        with torch.no_grad():
            p_lstm = float(self.net(x).squeeze())
        p_gbm = float(self.gbm.predict(window_features(window[None]))[0])
        prediction = max(self.w * p_lstm + (1 - self.w) * p_gbm, 0.0)

        per_input = self.w * deep.sum(0) + (1 - self.w) * tree.sum(0)
        order = np.argsort(-np.abs(per_input))
        return {
            "base_value": self.base_value,
            "prediction": prediction,
            "weight_lstm": self.w,
            "features": [
                {"sensor": self.inputs[i], "shap_value": float(per_input[i]),
                 "shap_lstm": float(self.w * deep[:, i].sum()),
                 "shap_gbm": float((1 - self.w) * tree[:, i].sum())}
                for i in order
            ],
            # temporal view only exists for the LSTM part (weighted to its share)
            "temporal": (self.w * np.abs(deep).sum(1)).tolist(),
            "heatmap": (self.w * deep.T).tolist(),           # (F, T) signed
            "heatmap_sensors": list(self.inputs),
        }
