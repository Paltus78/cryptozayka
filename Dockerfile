# ──────────────────────────────────────────────────────────────
#  Dockerfile  — единый образ для zayka API, worker и bot
#  Базовый python:3.11-slim + curl (нужен для health-check)
# ──────────────────────────────────────────────────────────────
FROM python:3.11-slim AS base

# ——— system deps ———
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# ——— python deps ———
WORKDIR /app
COPY requirements-runtime.txt .
RUN pip install --no-cache-dir -r requirements-runtime.txt

# ——— project source ———
COPY . .

# ——— runtime default ———
# (entrypoint задаётся в docker-compose для zayka/bot отдельно)
ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "cryptozayka"]

# ──────────────────────────────────────────────────────────────
