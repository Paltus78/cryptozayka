# syntax=docker/dockerfile:1.5
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# ─── system deps (asyncpg) ───────────────────────────
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        gcc build-essential libpq-dev \
 && rm -rf /var/lib/apt/lists/*

# ─── project files ───────────────────────────────────
COPY pyproject.toml README.md alembic.ini ./
COPY cryptozayka      ./cryptozayka
COPY alembic          ./alembic

# ─── faster install via constraints ─────────────────
RUN pip install --upgrade pip wheel pip-tools \
 && pip-compile pyproject.toml -o constraints.txt \
 && pip install --no-cache-dir -r constraints.txt

# ─── entrypoint: migrate + run uvicorn ──────────────
COPY docker-entrypoint.sh /usr/local/bin/entrypoint
RUN chmod +x /usr/local/bin/entrypoint

ENTRYPOINT ["entrypoint"]
CMD ["uvicorn", "cryptozayka.api:app", "--host", "0.0.0.0", "--port", "8000"]
