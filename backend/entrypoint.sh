#!/bin/sh
set -e
# 1. dataset (downloaded once into the mounted volume)
python -m scripts.download_data
# 2. train if no model artifacts are present
[ -f artifacts/meta.json ] || python -m aerohealth.ml.train
# 3. seed the fleet (no-op when already seeded)
python -m aerohealth.api.seed
exec uvicorn aerohealth.api.main:app --host 0.0.0.0 --port 8000
