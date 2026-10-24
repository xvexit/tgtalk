FROM ghcr.io/astral-sh/uv:python3.12-bookworm

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PATH=/opt/venv/bin:$PATH

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --group dev

CMD ["sleep", "infinity"]
