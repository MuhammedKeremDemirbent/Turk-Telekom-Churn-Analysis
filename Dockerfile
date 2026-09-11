FROM ghcr.io/astral-sh/uv:0.11.26 AS uv

FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev --no-install-project

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "uv run --no-sync python manage.py migrate && uv run --no-sync uvicorn config.asgi:application --host 0.0.0.0 --port 8000"]