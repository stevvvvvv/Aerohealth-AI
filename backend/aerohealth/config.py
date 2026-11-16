"""Central configuration for AeroHealth AI."""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("AEROHEALTH_DATA_DIR", BASE_DIR / "data" / "raw"))
ARTIFACTS_DIR = Path(os.getenv("AEROHEALTH_ARTIFACTS_DIR", BASE_DIR / "artifacts"))

DATABASE_URL = os.getenv(
    "DATABASE_URL", f"sqlite:///{BASE_DIR / 'aerohealth.db'}"
)

DEFAULT_DATASET = os.getenv("AEROHEALTH_DATASET", "FD001")

# --- Modelling constants -------------------------------------------------
RUL_CAP = 125          # piecewise-linear RUL target (standard for C-MAPSS)
WINDOW = 50            # cycles fed to the models (selected on validation engines)
N_SEEDS = 3            # LSTMs in the deep ensemble
AGE_SCALE = 200.0      # cycles-since-new is fed to the models as cycle / AGE_SCALE
INTERVAL_LEVEL = 0.90  # nominal coverage of the RUL prediction interval
SEED = 42

# --- Alerting thresholds (cycles) ----------------------------------------
CRITICAL_RUL = 20
WARNING_RUL = 50
ALERT_PROBABILITY = 0.5   # raise an RUL alert when P(RUL <= threshold) >= this
ANOMALY_PERSISTENCE = 3   # consecutive anomalous cycles before raising an alert

SETTING_COLS = ["setting_1", "setting_2", "setting_3"]
SENSOR_COLS = [f"s{i}" for i in range(1, 22)]
RAW_COLS = ["unit", "cycle", *SETTING_COLS, *SENSOR_COLS]

# Physical meaning of each C-MAPSS channel (Saxena et al., 2008).
SENSOR_INFO: dict[str, dict[str, str]] = {
    "s1": {"name": "T2", "description": "Total temperature at fan inlet", "unit": "°R"},
    "s2": {"name": "T24", "description": "Total temperature at LPC outlet", "unit": "°R"},
    "s3": {"name": "T30", "description": "Total temperature at HPC outlet", "unit": "°R"},
    "s4": {"name": "T50", "description": "Total temperature at LPT outlet", "unit": "°R"},
    "s5": {"name": "P2", "description": "Pressure at fan inlet", "unit": "psia"},
    "s6": {"name": "P15", "description": "Total pressure in bypass duct", "unit": "psia"},
    "s7": {"name": "P30", "description": "Total pressure at HPC outlet", "unit": "psia"},
    "s8": {"name": "Nf", "description": "Physical fan speed", "unit": "rpm"},
    "s9": {"name": "Nc", "description": "Physical core speed", "unit": "rpm"},
    "s10": {"name": "epr", "description": "Engine pressure ratio (P50/P2)", "unit": "-"},
    "s11": {"name": "Ps30", "description": "Static pressure at HPC outlet", "unit": "psia"},
    "s12": {"name": "phi", "description": "Fuel flow / Ps30", "unit": "pps/psi"},
    "s13": {"name": "NRf", "description": "Corrected fan speed", "unit": "rpm"},
    "s14": {"name": "NRc", "description": "Corrected core speed", "unit": "rpm"},
    "s15": {"name": "BPR", "description": "Bypass ratio", "unit": "-"},
    "s16": {"name": "farB", "description": "Burner fuel-air ratio", "unit": "-"},
    "s17": {"name": "htBleed", "description": "Bleed enthalpy", "unit": "-"},
    "s18": {"name": "Nf_dmd", "description": "Demanded fan speed", "unit": "rpm"},
    "s19": {"name": "PCNfR_dmd", "description": "Demanded corrected fan speed", "unit": "rpm"},
    "s20": {"name": "W31", "description": "HPT coolant bleed", "unit": "lbm/s"},
    "s21": {"name": "W32", "description": "LPT coolant bleed", "unit": "lbm/s"},
}

# Model inputs = informative sensors + engine age (cycles since new). Age is
# always known in operations: it is tracked in every engine logbook.
FEATURE_INFO: dict[str, dict[str, str]] = {
    **SENSOR_INFO,
    "age": {"name": "CSN", "description": "Cycles since new (engine age)", "unit": "cycles"},
}

DATASET_INFO = {
    "FD001": {"conditions": 1, "fault_modes": "HPC degradation"},
    "FD002": {"conditions": 6, "fault_modes": "HPC degradation"},
    "FD003": {"conditions": 1, "fault_modes": "HPC + fan degradation"},
    "FD004": {"conditions": 6, "fault_modes": "HPC + fan degradation"},
}
