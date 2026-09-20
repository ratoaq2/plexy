FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY pyproject.toml uv.lock README.md /app/
RUN uv sync --locked --no-install-project --no-dev
COPY plexy/ /app/plexy/
RUN uv sync --locked --no-dev


FROM python:3.13-slim

COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /

ENTRYPOINT ["plexy"]
CMD ["--help"]
