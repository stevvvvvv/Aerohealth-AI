from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, DateTime, Float, ForeignKey, Integer, String,
                        UniqueConstraint, create_engine)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from aerohealth import config

JSONType = JSON().with_variant(JSONB(), "postgresql")

_kwargs = {"connect_args": {"check_same_thread": False}} if config.DATABASE_URL.startswith("sqlite") else {"pool_pre_ping": True}
engine = create_engine(config.DATABASE_URL, **_kwargs)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Engine(Base):
    __tablename__ = "engines"
    id: Mapped[int] = mapped_column(primary_key=True)
    serial: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    dataset: Mapped[str] = mapped_column(String(8))
    unit: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="HEALTHY", index=True)
    rul_level: Mapped[str] = mapped_column(String(16), default="HEALTHY")
    anomaly_active: Mapped[bool] = mapped_column(Boolean, default=False)
    last_cycle: Mapped[int] = mapped_column(Integer, default=0)
    # Ground truth from the NASA test set (demo only: unknown in real operations)
    true_final_rul: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    readings: Mapped[list["SensorReading"]] = relationship(back_populates="engine", cascade="all, delete-orphan")
    predictions: Mapped[list["Prediction"]] = relationship(back_populates="engine", cascade="all, delete-orphan")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="engine", cascade="all, delete-orphan")


class SensorReading(Base):
    __tablename__ = "sensor_readings"
    __table_args__ = (UniqueConstraint("engine_id", "cycle"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    engine_id: Mapped[int] = mapped_column(ForeignKey("engines.id", ondelete="CASCADE"), index=True)
    cycle: Mapped[int] = mapped_column(Integer)
    settings: Mapped[dict] = mapped_column(JSONType)
    sensors: Mapped[dict] = mapped_column(JSONType)
    engine: Mapped[Engine] = relationship(back_populates="readings")


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (UniqueConstraint("engine_id", "cycle"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    engine_id: Mapped[int] = mapped_column(ForeignKey("engines.id", ondelete="CASCADE"), index=True)
    cycle: Mapped[int] = mapped_column(Integer)
    rul_mean: Mapped[float] = mapped_column(Float)
    rul_lower: Mapped[float] = mapped_column(Float)
    rul_upper: Mapped[float] = mapped_column(Float)
    p_critical: Mapped[float] = mapped_column(Float)
    p_warning: Mapped[float] = mapped_column(Float)
    health_index: Mapped[float] = mapped_column(Float)
    anomaly_score: Mapped[float] = mapped_column(Float)
    anomaly_confidence: Mapped[float] = mapped_column(Float)
    is_anomaly: Mapped[bool] = mapped_column(Boolean)
    top_deviation: Mapped[list] = mapped_column(JSONType)
    model_version: Mapped[str] = mapped_column(String(64))
    engine: Mapped[Engine] = relationship(back_populates="predictions")


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    engine_id: Mapped[int] = mapped_column(ForeignKey("engines.id", ondelete="CASCADE"), index=True)
    cycle: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(16))        # RUL | ANOMALY
    level: Mapped[str] = mapped_column(String(16), index=True)  # WARNING | CRITICAL
    confidence: Mapped[float] = mapped_column(Float)
    message: Mapped[str] = mapped_column(String(512))
    sensors: Mapped[list] = mapped_column(JSONType, default=list)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    engine: Mapped[Engine] = relationship(back_populates="alerts")


def init_db() -> None:
    Base.metadata.create_all(engine)
