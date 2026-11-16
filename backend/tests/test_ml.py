import numpy as np
import pandas as pd

from aerohealth.ml.data import add_train_rul, make_windows, unit_windows
from aerohealth.ml.metrics import nasa_score, rmse


def test_unit_windows_pads_and_aligns():
    v = np.arange(5, dtype=np.float32)[:, None]
    w = unit_windows(v, 3)
    assert w.shape == (5, 3, 1)
    assert w[0, :, 0].tolist() == [0, 0, 0]       # padded with first value
    assert w[-1, :, 0].tolist() == [2, 3, 4]      # last window = last 3 cycles


def test_train_rul_and_cap():
    df = pd.DataFrame({"unit": [1] * 200, "cycle": range(1, 201), "s2": 0.0})
    df = add_train_rul(df)
    assert df["rul"].iloc[0] == 199 and df["rul"].iloc[-1] == 0
    _, y, _ = make_windows(df, ["s2"], 30, cap=125)
    assert y.max() == 125


def test_metrics():
    assert rmse([10, 10], [10, 10]) == 0
    # late prediction (over-estimate) is penalised more than early
    assert nasa_score([50], [60]) > nasa_score([50], [40])
