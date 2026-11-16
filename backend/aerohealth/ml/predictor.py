"""Inference facade: loads trained artifacts and scores engine sequences."""
from __future__ import annotations

import json
from functools import cached_property
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch

from aerohealth import config
from aerohealth.ml.conformal import BinnedConformal
from aerohealth.ml.data import unit_windows
from aerohealth.ml.features import window_features
from aerohealth.ml.health import HealthModel
from aerohealth.ml.nets import RULLSTM, predict_members


class EnginePredictor:
    def __init__(self, artifacts_dir: Path | str | None = None):
        d = Path(artifacts_dir or config.ARTIFACTS_DIR)
        if not (d / "meta.json").exists():
            raise FileNotFoundError(
                f"No trained model in {d}. Run `python -m aerohealth.ml.train` first."
            )
        self.dir = d
        self.meta = json.loads((d / "meta.json").read_text())
        self.preprocessor = joblib.load(d / "preprocessor.joblib")
        self.health: HealthModel = joblib.load(d / "health.joblib")
        self.gbm = joblib.load(d / "gbm.joblib")
        self.conformal: BinnedConformal = joblib.load(d / "conformal.joblib")
        self.lstms: list[RULLSTM] = []
        for i in range(self.meta["n_lstm"]):
            ckpt = torch.load(d / f"lstm_{i}.pt", map_location="cpu", weights_only=False)
            m = RULLSTM(**ckpt["config"])
            m.load_state_dict(ckpt["state_dict"])
            self.lstms.append(m.eval())
        self.sensors: list[str] = self.meta["sensors"]   # monitored sensors
        self.inputs: list[str] = self.meta["inputs"]     # sensors + age
        self.window: int = self.meta["window"]
        self.w: float = self.meta["weight_lstm"]

    @property
    def version(self) -> str:
        return self.meta["model_version"]

    @cached_property
    def explainer(self):
        from aerohealth.ml.explain import EnsembleExplainer
        background = np.load(self.dir / "shap_background.npy")
        return EnsembleExplainer(self.lstms, self.gbm, self.w, background, self.inputs)

    # ------------------------------------------------------------------
    def _windows(self, unit_df: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
        df = unit_df.sort_values("cycle").reset_index(drop=True)
        norm_df = self.preprocessor.transform(df)
        return norm_df, unit_windows(norm_df[self.inputs].to_numpy(np.float32), self.window)

    def predict_windows(self, windows: np.ndarray) -> dict[str, np.ndarray]:
        members = predict_members(self.lstms, windows)
        lstm = members.mean(0)
        gbm = np.clip(self.gbm.predict(window_features(windows)), 0, None)
        mean = self.w * lstm + (1 - self.w) * gbm
        lo, hi = self.conformal.interval(mean)
        return {
            "rul_mean": mean, "rul_lower": lo, "rul_upper": hi,
            "rul_lstm": lstm, "rul_gbm": gbm, "rul_spread": members.std(0),
            "p_critical": self.conformal.prob_below(mean, config.CRITICAL_RUL),
            "p_warning": self.conformal.prob_below(mean, config.WARNING_RUL),
        }

    def predict_unit(self, unit_df: pd.DataFrame) -> pd.DataFrame:
        """Score every cycle of one engine. ``unit_df`` holds raw sensor columns."""
        norm_df, windows = self._windows(unit_df)
        out = self.health.analyse_unit(norm_df)
        for k, v in self.predict_windows(windows).items():
            out[k] = v
        return out

    def explain_cycle(self, unit_df: pd.DataFrame, cycle: int) -> dict:
        norm_df, windows = self._windows(unit_df)
        idx = min(int(np.searchsorted(norm_df["cycle"].to_numpy(), cycle)), len(windows) - 1)
        result = self.explainer.explain(windows[idx])
        result["cycle"] = int(norm_df["cycle"].iloc[idx])
        start = result["cycle"] - self.window + 1
        result["window_cycles"] = list(range(start, result["cycle"] + 1))
        return result
