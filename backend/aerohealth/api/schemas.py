from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class EngineSummary(ORM):
    id: int
    serial: str
    dataset: str
    status: str
    last_cycle: int
    rul_mean: float | None = None
    rul_lower: float | None = None
    rul_upper: float | None = None
    health_index: float | None = None
    open_alerts: int = 0


class FleetResponse(BaseModel):
    engines: list[EngineSummary]
    counts: dict[str, int]
    model_version: str


class PredictionOut(ORM):
    cycle: int
    rul_mean: float
    rul_lower: float
    rul_upper: float
    p_critical: float
    p_warning: float
    health_index: float
    anomaly_score: float
    anomaly_confidence: float
    is_anomaly: bool
    top_deviation: list[str]
    true_rul: int | None = None


class AlertOut(ORM):
    id: int
    engine_id: int
    engine_serial: str | None = None
    cycle: int
    kind: str
    level: str
    confidence: float
    message: str
    sensors: list[str]
    acknowledged: bool
    created_at: datetime


class EngineDetail(EngineSummary):
    true_final_rul: int | None
    anomaly_threshold: float
    latest: PredictionOut | None


class SensorSeries(BaseModel):
    cycles: list[int]
    series: dict[str, list[float]]


class CycleIn(BaseModel):
    cycle: int | None = Field(None, description="Defaults to last cycle + 1")
    settings: dict[str, float] = Field(..., examples=[{"setting_1": 0.0, "setting_2": 0.0, "setting_3": 100.0}])
    sensors: dict[str, float] = Field(..., description="s1 … s21 raw values")


class IngestResult(BaseModel):
    engine_id: int
    cycle: int
    prediction: PredictionOut
    new_alerts: list[AlertOut]
