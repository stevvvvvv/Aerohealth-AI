"""Populate the database with the C-MAPSS test fleet and score every engine.

Usage:
    python -m aerohealth.api.seed [--dataset FD001] [--limit 100] [--reset]
"""
from __future__ import annotations

import argparse
import time

from sqlalchemy import func, select

from aerohealth import config
from aerohealth.api.db import Base, Engine, SensorReading, SessionLocal, engine, init_db
from aerohealth.api.services import score_engine
from aerohealth.ml import data as D


def seed(dataset: str = config.DEFAULT_DATASET, limit: int | None = None, reset: bool = False) -> None:
    if reset:
        Base.metadata.drop_all(engine)
    init_db()
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(Engine)):
            print("Database already seeded — skipping (use --reset to rebuild).")
            return
        test = D.load_raw(dataset, "test")
        final_rul = D.load_test_rul(dataset)
        units = sorted(test["unit"].unique())[:limit]
        t0 = time.time()
        for u in units:
            g = test[test["unit"] == u]
            eng = Engine(serial=f"ESN-{dataset[-1]}{u:03d}", dataset=dataset, unit=int(u),
                         true_final_rul=int(final_rul[u]))
            db.add(eng)
            db.flush()
            db.bulk_insert_mappings(SensorReading, [
                dict(engine_id=eng.id, cycle=int(r["cycle"]),
                     settings={c: float(r[c]) for c in config.SETTING_COLS},
                     sensors={c: float(r[c]) for c in config.SENSOR_COLS})
                for _, r in g.iterrows()
            ])
            score_engine(db, eng)
            print(f"  {eng.serial}: {len(g)} cycles -> {eng.status}")
        print(f"Seeded {len(units)} engines in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", default=config.DEFAULT_DATASET)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--reset", action="store_true")
    a = p.parse_args()
    seed(a.dataset, a.limit, a.reset)
