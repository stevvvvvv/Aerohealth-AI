"""AeroHealth AI — REST API."""
from __future__ import annotations

from collections import Counter
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from aerohealth import config
from aerohealth.api import schemas as S
from aerohealth.api.db import Alert, Engine, Prediction, SensorReading, SessionLocal, init_db
from aerohealth.api.services import get_predictor, readings_frame, score_engine

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="AeroHealth AI",
    description="Predictive maintenance API for turbofan engines (NASA C-MAPSS).",
    version="1.0.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_explain_cache: dict[tuple[int, int], dict] = {}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _engine_or_404(db: Session, engine_id: int) -> Engine:
    eng = db.get(Engine, engine_id)
    if eng is None:
        raise HTTPException(404, f"Engine {engine_id} not found")
    return eng


def _pred_out(p: Prediction, eng: Engine) -> S.PredictionOut:
    out = S.PredictionOut.model_validate(p)
    if eng.true_final_rul is not None:
        out.true_rul = eng.true_final_rul + (eng.last_cycle - p.cycle)
    return out


def _alert_out(a: Alert, serial: str | None = None) -> S.AlertOut:
    out = S.AlertOut.model_validate(a)
    out.engine_serial = serial
    return out


# ---------------------------------------------------------------------------
@app.get("/api/health", tags=["system"])
def health():
    p = get_predictor()
    return {"status": "ok", "model_version": p.version}


@app.get("/api/model", tags=["system"])
def model_card():
    m = get_predictor().meta
    return {
        "model_version": m["model_version"], "dataset": m["dataset"],
        "trained_at": m["trained_at"], "window": m["window"], "rul_cap": m["rul_cap"],
        "features": [{"sensor": s, **config.SENSOR_INFO[s]} for s in m["features"]],
        "metrics": m["metrics"], "history": m["history"],
        "thresholds": {"critical_rul": config.CRITICAL_RUL, "warning_rul": config.WARNING_RUL,
                       "alert_probability": config.ALERT_PROBABILITY,
                       "anomaly_persistence": config.ANOMALY_PERSISTENCE},
    }


@app.get("/api/sensors", tags=["system"])
def sensors():
    used = set(get_predictor().features)
    return [{"sensor": s, **info, "used_by_model": s in used} for s, info in config.SENSOR_INFO.items()]


@app.get("/api/fleet", response_model=S.FleetResponse, tags=["fleet"])
def fleet(db: Session = Depends(get_db)):
    rows = db.execute(
        select(Engine, Prediction).outerjoin(
            Prediction, and_(Prediction.engine_id == Engine.id, Prediction.cycle == Engine.last_cycle)
        ).order_by(Engine.id)
    ).all()
    open_alerts = dict(db.execute(
        select(Alert.engine_id, func.count()).where(~Alert.acknowledged).group_by(Alert.engine_id)
    ).all())
    engines = []
    for eng, p in rows:
        s = S.EngineSummary.model_validate(eng)
        if p is not None:
            s.rul_mean, s.rul_lower, s.rul_upper = p.rul_mean, p.rul_lower, p.rul_upper
            s.health_index = p.health_index
        s.open_alerts = open_alerts.get(eng.id, 0)
        engines.append(s)
    return S.FleetResponse(
        engines=engines, counts=dict(Counter(e.status for e in engines)),
        model_version=get_predictor().version,
    )


@app.get("/api/engines/{engine_id}", response_model=S.EngineDetail, tags=["engines"])
def engine_detail(engine_id: int, db: Session = Depends(get_db)):
    eng = _engine_or_404(db, engine_id)
    p = db.scalar(select(Prediction).where(Prediction.engine_id == eng.id,
                                           Prediction.cycle == eng.last_cycle))
    n_open = db.scalar(select(func.count()).where(Alert.engine_id == eng.id, ~Alert.acknowledged))
    d = S.EngineDetail(
        **S.EngineSummary.model_validate(eng).model_dump(),
        true_final_rul=eng.true_final_rul,
        anomaly_threshold=get_predictor().health.threshold,
        latest=_pred_out(p, eng) if p else None,
    )
    if p:
        d.rul_mean, d.rul_lower, d.rul_upper, d.health_index = p.rul_mean, p.rul_lower, p.rul_upper, p.health_index
    d.open_alerts = n_open or 0
    return d


@app.get("/api/engines/{engine_id}/predictions", response_model=list[S.PredictionOut], tags=["engines"])
def engine_predictions(engine_id: int, db: Session = Depends(get_db)):
    eng = _engine_or_404(db, engine_id)
    preds = db.scalars(select(Prediction).where(Prediction.engine_id == eng.id).order_by(Prediction.cycle))
    return [_pred_out(p, eng) for p in preds]


@app.get("/api/engines/{engine_id}/sensors", response_model=S.SensorSeries, tags=["engines"])
def engine_sensors(engine_id: int, sensors: str | None = Query(None, description="Comma separated, e.g. s2,s3"),
                   db: Session = Depends(get_db)):
    eng = _engine_or_404(db, engine_id)
    df = readings_frame(db, eng)
    wanted = sensors.split(",") if sensors else get_predictor().features
    unknown = [s for s in wanted if s not in config.SENSOR_INFO]
    if unknown:
        raise HTTPException(422, f"Unknown sensors: {unknown}")
    return S.SensorSeries(cycles=df["cycle"].tolist() if not df.empty else [],
                          series={s: df[s].round(4).tolist() for s in wanted} if not df.empty else {})


@app.get("/api/engines/{engine_id}/explain", tags=["engines"])
def engine_explain(engine_id: int, cycle: int | None = None, db: Session = Depends(get_db)):
    """SHAP attribution of the RUL prediction at a given cycle (default: latest)."""
    eng = _engine_or_404(db, engine_id)
    cycle = cycle or eng.last_cycle
    key = (eng.id, cycle)
    if key not in _explain_cache:
        result = get_predictor().explain_cycle(readings_frame(db, eng), cycle)
        for f in result["features"]:
            f.update(config.SENSOR_INFO[f["sensor"]])
        _explain_cache[key] = result
    return _explain_cache[key]


@app.post("/api/engines/{engine_id}/cycles", response_model=S.IngestResult, tags=["engines"])
def ingest_cycle(engine_id: int, payload: S.CycleIn, db: Session = Depends(get_db)):
    """Ingest one new flight cycle of sensor data, re-score and raise alerts."""
    eng = _engine_or_404(db, engine_id)
    missing = [c for c in config.SETTING_COLS if c not in payload.settings] + \
              [s for s in config.SENSOR_COLS if s not in payload.sensors]
    if missing:
        raise HTTPException(422, f"Missing fields: {missing}")
    cycle = payload.cycle or eng.last_cycle + 1
    if cycle <= eng.last_cycle:
        raise HTTPException(409, f"Cycle {cycle} already recorded (last = {eng.last_cycle})")
    db.add(SensorReading(engine_id=eng.id, cycle=cycle,
                         settings={k: payload.settings[k] for k in config.SETTING_COLS},
                         sensors={k: payload.sensors[k] for k in config.SENSOR_COLS}))
    if eng.true_final_rul is not None:  # ground truth no longer valid once live data arrives
        eng.true_final_rul = None
    db.flush()
    before = {a.id for a in eng.alerts}
    score_engine(db, eng, from_cycle=cycle)
    db.refresh(eng)
    p = db.scalar(select(Prediction).where(Prediction.engine_id == eng.id, Prediction.cycle == cycle))
    new_alerts = [_alert_out(a, eng.serial) for a in eng.alerts if a.id not in before]
    return S.IngestResult(engine_id=eng.id, cycle=cycle, prediction=_pred_out(p, eng), new_alerts=new_alerts)


@app.get("/api/alerts", response_model=list[S.AlertOut], tags=["alerts"])
def list_alerts(engine_id: int | None = None, level: str | None = None, kind: str | None = None,
                open_only: bool = False, limit: int = Query(200, le=1000), db: Session = Depends(get_db)):
    q = select(Alert, Engine.serial).join(Engine)
    if engine_id:
        q = q.where(Alert.engine_id == engine_id)
    if level:
        q = q.where(Alert.level == level.upper())
    if kind:
        q = q.where(Alert.kind == kind.upper())
    if open_only:
        q = q.where(~Alert.acknowledged)
    q = q.order_by(Alert.level.asc(), Alert.engine_id, Alert.cycle.desc()).limit(limit)
    return [_alert_out(a, serial) for a, serial in db.execute(q).all()]


@app.patch("/api/alerts/{alert_id}/ack", response_model=S.AlertOut, tags=["alerts"])
def acknowledge(alert_id: int, db: Session = Depends(get_db)):
    a = db.get(Alert, alert_id)
    if a is None:
        raise HTTPException(404, "Alert not found")
    a.acknowledged = True
    db.commit()
    return _alert_out(a, a.engine.serial)
