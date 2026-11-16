"""SHAP explanations for the LSTM RUL model.

``shap.GradientExplainer`` (expected gradients) attributes the prediction to
every (time step, sensor) cell of the input window. We aggregate it:
  * per sensor  -> which measurements drive the RUL estimate,
  * per cycle   -> which part of the recent history matters most.
"""
from __future__ import annotations

import numpy as np
import shap
import torch

from aerohealth.ml.lstm import RULLSTM


class _Deterministic(torch.nn.Module):
    """Wrapper returning (B, 1) and always in eval mode (no MC dropout)."""

    def __init__(self, model: RULLSTM):
        super().__init__()
        self.model = model

    def forward(self, x):
        return self.model(x).unsqueeze(-1)


class RULExplainer:
    def __init__(self, model: RULLSTM, background: np.ndarray, features: list[str]):
        self.features = features
        self.wrapped = _Deterministic(model).eval()
        # cuDNN-free LSTM backward needs train mode on some backends; CPU is fine in eval.
        self.background = torch.from_numpy(background.astype(np.float32))
        self.explainer = shap.GradientExplainer(self.wrapped, self.background)
        with torch.no_grad():
            self.base_value = float(self.wrapped(self.background).mean())

    def explain(self, window: np.ndarray, nsamples: int = 200) -> dict:
        x = torch.from_numpy(window[None].astype(np.float32))
        values = self.explainer.shap_values(x, nsamples=nsamples, rseed=0)
        values = np.asarray(values).reshape(window.shape)  # (T, F)
        with torch.no_grad():
            prediction = float(self.wrapped(x).squeeze())
        per_sensor = values.sum(0)
        order = np.argsort(-np.abs(per_sensor))
        return {
            "base_value": self.base_value,
            "prediction": max(prediction, 0.0),
            "features": [
                {"sensor": self.features[i], "shap_value": float(per_sensor[i]),
                 "mean_input": float(window[:, i].mean())}
                for i in order
            ],
            "temporal": np.abs(values).sum(1).tolist(),     # importance per time step
            "heatmap": values.T.tolist(),                    # (F, T) signed
            "heatmap_sensors": list(self.features),
        }
