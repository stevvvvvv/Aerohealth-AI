"""Loading, labelling and preprocessing of the NASA C-MAPSS turbofan dataset."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

from aerohealth import config


# ---------------------------------------------------------------------------
# Loading & labelling
# ---------------------------------------------------------------------------
def load_raw(dataset: str, split: str, data_dir: Path | None = None) -> pd.DataFrame:
    """Load ``train`` or ``test`` file of a C-MAPSS sub-dataset."""
    data_dir = Path(data_dir or config.DATA_DIR)
    path = data_dir / f"{split}_{dataset}.txt"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run `python -m scripts.download_data` first."
        )
    df = pd.read_csv(path, sep=r"\s+", header=None, names=config.RAW_COLS)
    df[["unit", "cycle"]] = df[["unit", "cycle"]].astype(int)
    return df


def load_test_rul(dataset: str, data_dir: Path | None = None) -> pd.Series:
    data_dir = Path(data_dir or config.DATA_DIR)
    rul = pd.read_csv(data_dir / f"RUL_{dataset}.txt", header=None).iloc[:, 0]
    rul.index = np.arange(1, len(rul) + 1)
    rul.index.name = "unit"
    return rul.astype(int)


def add_train_rul(df: pd.DataFrame) -> pd.DataFrame:
    """Run-to-failure data: RUL = last cycle - current cycle."""
    out = df.copy()
    out["rul"] = out.groupby("unit")["cycle"].transform("max") - out["cycle"]
    return out


def add_test_rul(df: pd.DataFrame, final_rul: pd.Series) -> pd.DataFrame:
    """Truncated test data: RUL = RUL at last observed cycle + remaining cycles."""
    out = df.copy()
    last = out.groupby("unit")["cycle"].transform("max")
    out["rul"] = out["unit"].map(final_rul) + (last - out["cycle"])
    return out


# ---------------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------------
@dataclass
class Preprocessor:
    """Operating-condition aware normaliser + feature selection.

    FD002/FD004 mix six flight regimes; sensor levels depend mostly on the
    regime, not on degradation. Normalising each regime separately removes
    that effect so the models only see degradation trends.
    """

    n_conditions: int = 1
    smooth_alpha: float | None = None  # causal EWMA per engine, reduces sensor noise
    std_threshold: float = 1e-3
    features: list[str] = field(default_factory=list)
    kmeans: KMeans | None = None
    stats: dict[int, tuple[pd.Series, pd.Series]] = field(default_factory=dict)

    def _conditions(self, df: pd.DataFrame) -> np.ndarray:
        if self.n_conditions == 1 or self.kmeans is None:
            return np.zeros(len(df), dtype=int)
        return self.kmeans.predict(df[config.SETTING_COLS].to_numpy())

    def fit(self, df: pd.DataFrame) -> "Preprocessor":
        if self.n_conditions > 1:
            self.kmeans = KMeans(self.n_conditions, n_init=10, random_state=config.SEED)
            self.kmeans.fit(df[config.SETTING_COLS].to_numpy())
        cond = self._conditions(df)
        self.stats = {}
        for c in np.unique(cond):
            part = df.loc[cond == c, config.SENSOR_COLS]
            self.stats[int(c)] = (part.mean(), part.std().replace(0, 1.0))
        normed = self._normalise(df, cond)
        # Keep only informative sensors (constant channels carry no signal).
        stds = normed[config.SENSOR_COLS].std()
        raw_rel = df[config.SENSOR_COLS].std() / df[config.SENSOR_COLS].mean().abs().clip(lower=1e-9)
        self.features = [
            s for s in config.SENSOR_COLS
            if stds[s] > self.std_threshold and raw_rel[s] > 1e-5
        ]
        return self

    def _normalise(self, df: pd.DataFrame, cond: np.ndarray) -> pd.DataFrame:
        out = df.copy()
        values = out[config.SENSOR_COLS].astype(float)
        for c, (mu, sd) in self.stats.items():
            mask = cond == c
            values.loc[mask] = (values.loc[mask] - mu) / sd
        out[config.SENSOR_COLS] = values
        return out

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        out = self._normalise(df, self._conditions(df))
        if self.smooth_alpha:
            out[config.SENSOR_COLS] = out.groupby("unit")[config.SENSOR_COLS].transform(
                lambda s: s.ewm(alpha=self.smooth_alpha, adjust=True).mean()
            )
        return out


# ---------------------------------------------------------------------------
# Windowing
# ---------------------------------------------------------------------------
def _pad(values: np.ndarray, window: int) -> np.ndarray:
    """Left-pad short sequences by repeating the first observation."""
    if len(values) >= window:
        return values
    pad = np.repeat(values[:1], window - len(values), axis=0)
    return np.vstack([pad, values])


def unit_windows(values: np.ndarray, window: int) -> np.ndarray:
    """One window ending at *every* cycle of a unit -> (n_cycles, window, n_feat)."""
    n = len(values)
    padded = _pad(values, window + n - 1)
    idx = np.arange(window)[None, :] + np.arange(n)[:, None]
    return padded[idx].astype(np.float32)


def make_windows(
    df: pd.DataFrame, features: list[str], window: int, cap: int | None = config.RUL_CAP,
    last_only: bool = False,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build (X, y, unit_ids) arrays from a normalised dataframe with a ``rul`` column."""
    xs, ys, units = [], [], []
    for unit, g in df.groupby("unit", sort=True):
        vals = g[features].to_numpy(dtype=np.float32)
        w = unit_windows(vals, window)
        y = g["rul"].to_numpy(dtype=np.float32)
        if last_only:
            w, y = w[-1:], y[-1:]
        xs.append(w)
        ys.append(y)
        units.append(np.full(len(y), unit))
    y = np.concatenate(ys)
    if cap is not None:
        y = np.minimum(y, cap)
    return np.concatenate(xs), y, np.concatenate(units)
