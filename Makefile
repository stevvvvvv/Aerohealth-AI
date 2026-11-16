.PHONY: up down data train seed api web test

up:        ## full stack (Postgres + API + dashboard) on http://localhost:3000
	docker compose up --build

down:
	docker compose down

data:      ## download NASA C-MAPSS
	cd backend && python -m scripts.download_data

train:     ## retrain models -> backend/artifacts
	cd backend && python -m aerohealth.ml.train --dataset FD001

seed:      ## load the test fleet into the database (SQLite by default)
	cd backend && python -m aerohealth.api.seed --reset

api:
	cd backend && uvicorn aerohealth.api.main:app --reload

web:
	cd frontend && npm run dev

test:
	cd backend && python -m pytest -q
