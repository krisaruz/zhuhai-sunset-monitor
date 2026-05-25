FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir . 2>/dev/null || pip install --no-cache-dir \
    fastapi uvicorn httpx sqlalchemy aiosqlite alembic pydantic-settings ephem apscheduler jinja2

COPY src/ src/
COPY templates/ templates/
COPY alembic/ alembic/
COPY alembic.ini .

RUN mkdir -p data

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head 2>/dev/null || true && uvicorn src.main:app --host 0.0.0.0 --port 8000"]
