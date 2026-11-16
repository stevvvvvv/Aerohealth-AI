# Single-container demo for Hugging Face Spaces: dashboard + API + SQLite.
# The fleet is seeded at build time, so the Space starts in a few seconds.

FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

# Spaces run the container as uid 1000
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    DATABASE_URL=sqlite:////home/user/app/aerohealth.db \
    STATIC_DIR=/home/user/app/static \
    OMP_NUM_THREADS=2
WORKDIR /home/user/app

COPY --chown=user backend/aerohealth ./aerohealth
COPY --chown=user backend/scripts ./scripts
COPY --chown=user backend/artifacts ./artifacts
COPY --chown=user --from=web /web/dist ./static

RUN python -m scripts.download_data && python -m aerohealth.api.seed

EXPOSE 7860
CMD ["uvicorn", "aerohealth.api.main:app", "--host", "0.0.0.0", "--port", "7860"]
