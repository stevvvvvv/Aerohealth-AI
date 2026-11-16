"""Export the API responses as static JSON for the GitHub Pages demo.

Every number in the static demo comes from the real models: the fleet is
scored by the API exactly as in Docker, then the responses are frozen.
SHAP explanations are precomputed every ``--shap-every`` cycles plus the
latest cycle of each engine.

Usage:
    python -m aerohealth.api.seed --reset
    python -m scripts.export_static --out ../frontend/static-data
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from aerohealth import config
from aerohealth.api.main import app


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, separators=(",", ":"), default=str))


def main(out: Path, shap_every: int) -> None:
    if out.exists():
        shutil.rmtree(out)
    with TestClient(app) as c:
        get = lambda url: c.get(url).raise_for_status().json()  # noqa: E731
        fleet = get("/api/fleet")
        dump(out / "fleet.json", fleet)
        dump(out / "model.json", get("/api/model"))
        dump(out / "sensors.json", get("/api/sensors"))
        dump(out / "alerts.json", get("/api/alerts?limit=1000"))
        all_sensors = ",".join(config.SENSOR_COLS)
        for e in fleet["engines"]:
            eid, last = e["id"], e["last_cycle"]
            base = out / "engines" / str(eid)
            dump(base / "detail.json", get(f"/api/engines/{eid}"))
            dump(base / "predictions.json", get(f"/api/engines/{eid}/predictions"))
            dump(base / "sensors.json", get(f"/api/engines/{eid}/sensors?sensors={all_sensors}"))
            cycles = sorted({*range(shap_every, last + 1, shap_every), last})
            for cy in cycles:
                ex = get(f"/api/engines/{eid}/explain?cycle={cy}")
                for k in ("heatmap",):  # round to keep the files small
                    ex[k] = [[round(v, 3) for v in row] for row in ex[k]]
                dump(base / "explain" / f"{cy}.json", ex)
            dump(base / "explain" / "index.json", cycles)
            print(f"{e['serial']}: {len(cycles)} explanations")
    size = sum(f.stat().st_size for f in out.rglob("*.json")) / 1e6
    print(f"exported to {out} ({size:.1f} MB)")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=Path("../frontend/static-data"))
    p.add_argument("--shap-every", type=int, default=10)
    a = p.parse_args()
    main(a.out, a.shap_every)
