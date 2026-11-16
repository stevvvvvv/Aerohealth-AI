"""Business logic: inference orchestration and alerting rules."""
from __future__ import annotations

from functools import lru_cache

import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from aerohealth import config
from aerohealth.api.db import Alert, Engine, Prediction, SensorReading
from aerohealth.ml.predictor import EnginePredictor

SEVERITY = {"HEALTHY": 0, "WATCH": 1, "WARNING": 2, "CRITICAL": 3}
HYSTERESIS = 0.25      # probability margin required to clear an RUL level
ANOMALY_RESET = 15     # quiet cycles required to clear an anomaly state


@lru_cache(maxsize=1)
def get_predictor() -> EnginePredictor:
    return EnginePredictor()


def readings_frame(db: Session, engine: Engine) -> pd.DataFrame:
    rows = db.execute(
        select(SensorReading.cycle, SensorReading.settings, SensorReading.sensors)
        .where(SensorReading.engine_id == engine.id).order_by(SensorReading.cycle)
    ).all()
    records = [{"unit": engine.unit, "cycle": c, **st, **se} for c, st, se in rows]
    return pd.DataFrame.from_records(records)


def sensor_label(s: str) -> str:
    return config.SENSOR_INFO[s]["name"]


def rul_level(p_critical: float, p_warning: float) -> str:
    if p_critical >= config.ALERT_PROBABILITY:
        return "CRITICAL"
    if p_warning >= config.ALERT_PROBABILITY:
        return "WARNING"
    return "HEALTHY"


def score_engine(db: Session, engine: Engine, from_cycle: int | None = None) -> int:
    """(Re)score an engine and raise alerts for cycles >= ``from_cycle``.

    The whole sequence is re-scored (windows need history) but only new
    cycles are written, and alerts follow state transitions so an engineer
    is not spammed with one alert per cycle.
    """
    predictor = get_predictor()
    df = readings_frame(db, engine)
    if df.empty:
        return 0
    res = predictor.predict_unit(df)
    if from_cycle is None:
        db.execute(delete(Prediction).where(Prediction.engine_id == engine.id))
        db.execute(delete(Alert).where(Alert.engine_id == engine.id))
        from_cycle = int(res["cycle"].min())
    else:
        db.execute(delete(Prediction).where(Prediction.engine_id == engine.id,
                                            Prediction.cycle >= from_cycle))

    # Replay the alert state machine over the full history (deterministic),
    # emitting alerts only for the new cycles. Hysteresis avoids flapping.
    preds, alerts = [], []
    level, anomaly_active, calm = "HEALTHY", False, 0
    for r in res.itertuples(index=False):
        is_new = r.cycle >= from_cycle
        if is_new:
            preds.append(dict(
                engine_id=engine.id, cycle=int(r.cycle), rul_mean=float(r.rul_mean),
                rul_lower=float(r.rul_lower), rul_upper=float(r.rul_upper),
                p_critical=float(r.p_critical), p_warning=float(r.p_warning),
                health_index=float(r.health_index), anomaly_score=float(r.anomaly_score),
                anomaly_confidence=float(r.anomaly_confidence), is_anomaly=bool(r.is_anomaly),
                top_deviation=list(r.top_deviation), model_version=predictor.version,
            ))
        target = rul_level(r.p_critical, r.p_warning)
        if SEVERITY[target] > SEVERITY[level]:
            if is_new:
                thr = config.CRITICAL_RUL if target == "CRITICAL" else config.WARNING_RUL
                p = r.p_critical if target == "CRITICAL" else r.p_warning
                alerts.append(Alert(
                    engine_id=engine.id, cycle=int(r.cycle), kind="RUL", level=target,
                    confidence=float(p), sensors=[],
                    message=(f"Predicted RUL {r.rul_mean:.0f} cycles "
                             f"[{r.rul_lower:.0f}–{r.rul_upper:.0f}] — P(RUL ≤ {thr}) = {p:.0%}. "
                             + ("Schedule removal / shop visit." if target == "CRITICAL"
                                else "Plan inspection at next opportunity.")),
                ))
            level = target
        elif SEVERITY[target] < SEVERITY[level]:
            # de-escalate only once the probability is clearly below the trigger
            p = r.p_critical if level == "CRITICAL" else r.p_warning
            if p < config.ALERT_PROBABILITY - HYSTERESIS:
                level = target
        if r.is_anomaly:
            calm = 0
            if not anomaly_active:
                anomaly_active = True
                if is_new:
                    names = ", ".join(sensor_label(s) for s in r.top_deviation)
                    alerts.append(Alert(
                        engine_id=engine.id, cycle=int(r.cycle), kind="ANOMALY", level="WARNING",
                        confidence=float(r.anomaly_confidence), sensors=list(r.top_deviation),
                        message=(f"Persistent deviation from healthy baseline "
                                 f"({config.ANOMALY_PERSISTENCE}+ cycles). Main contributors: {names}."),
                    ))
        else:
            calm += 1
            if calm >= ANOMALY_RESET:
                anomaly_active = False
    engine.rul_level, engine.anomaly_active = level, anomaly_active

    if preds:
        db.bulk_insert_mappings(Prediction, preds)
    db.add_all(alerts)
    last = res.iloc[-1]
    engine.last_cycle = int(last["cycle"])
    engine.status = engine.rul_level if engine.rul_level != "HEALTHY" else (
        "WATCH" if engine.anomaly_active else "HEALTHY")
    db.commit()
    return len(preds)
