"""Inference facade: loads trained artifacts and scores engine sequences."""
from __future__ import annotations

import json
from functools import cached_property
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch
from scipy.stats import norm

from aerohealth import config
from aerohealth.ml.data import unit_windows
from aerohealth.ml.health import HealthModel
from aerohealth.ml.lstm import RULLSTM, predict_mc

Z = norm.ppf(0.5 + config.INTERVAL_LEVEL / 2)


class EnginePredictor:
    def __init__(self, artifacts_dir: Path | str | None = None):
        d = Path(artifacts_dir or config.ARTIFACTS_DIR)
        if not (d / "lstm.pt").exists():
            raise FileNotFoundError(
                f"No trained model in {d}. Run `python -m aerohealth.ml.train` first."
            )
        self.dir = d
        self.meta = json.loads((d / "meta.json").read_text())
        self.preprocessor = joblib.load(d / "preprocessor.joblib")
        self.health: HealthModel = joblib.load(d / "health.joblib")
        ckpt = torch.load(d / "lstm.pt", map_location="cpu", weights_only=False)
        self.model = RULLSTM(**ckpt["config"])
        self.model.load_state_dict(ckpt["state_dict"])
        self.model.eval()
        self.features: list[str] = self.meta["features"]
        self.window: int = self.meta["window"]
        self.k: float = self.meta["calibration_k"]

    @property
    def version(self) -> str:
        return self.meta["model_version"]

    @cached_property
    def explainer(self):
        from aerohealth.ml.explain import RULExplainer
        background = np.load(self.dir / "shap_background.npy")
        return RULExplainer(self.model, background, self.features)

    # ------------------------------------------------------------------
    def _windows(self, unit_df: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
        df = unit_df.sort_values("cycle").reset_index(drop=True)
        norm_df = self.preprocessor.transform(df)
        return norm_df, unit_windows(norm_df[self.features].to_numpy(np.float32), self.window)

    def predict_unit(self, unit_df: pd.DataFrame, samples: int = config.MC_SAMPLES) -> pd.DataFrame:
        """Score every cycle of one engine. ``unit_df`` holds raw sensor columns."""
        norm_df, windows = self._windows(unit_df)
        mean, std = predict_mc(self.model, windows, samples=samples)
        half = self.k * std
        sd_eff = np.maximum(half / Z, 1e-3)
        out = self.health.analyse_unit(norm_df)
        out["rul_mean"] = mean
        out["rul_std"] = std
        out["rul_lower"] = np.clip(mean - half, 0, None)
        out["rul_upper"] = mean + half
        out["p_critical"] = norm.cdf((config.CRITICAL_RUL - mean) / sd_eff)
        out["p_warning"] = norm.cdf((config.WARNING_RUL - mean) / sd_eff)
        return out

    def explain_cycle(self, unit_df: pd.DataFrame, cycle: int) -> dict:
        norm_df, windows = self._windows(unit_df)
        idx = int(np.searchsorted(norm_df["cycle"].to_numpy(), cycle))
        idx = min(idx, len(windows) - 1)
        result = self.explainer.explain(windows[idx])
        result["cycle"] = int(norm_df["cycle"].iloc[idx])
        start = result["cycle"] - self.window + 1
        result["window_cycles"] = list(range(start, result["cycle"] + 1))
        return result
