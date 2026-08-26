# GİRVAK content API.
#
# Two stages: one resolves dependencies from the committed lockfile, the runtime
# stage carries only the interpreter, those dependencies, and the app.
# Digest-pinned so an upgrade is a visible diff, never a silent one.
FROM python:3.12-slim@sha256:7a8b475003c4fe15a2cd4e55e5cfc2f3560bdc9333d624f24cdd6d4340fd7a17 AS deps

# uv 0.11.24 — the version this project's lockfile was written with.
COPY --from=ghcr.io/astral-sh/uv:0.11.24@sha256:99ea34acedc870ba4ad11a1f540a1c04267c9f30aadc465a94406f52dfda2c36 /uv /usr/local/bin/uv

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /build
COPY pyproject.toml uv.lock ./
# --frozen: install exactly what the lockfile says, never re-resolve.
RUN uv sync --frozen --no-dev


FROM python:3.12-slim@sha256:7a8b475003c4fe15a2cd4e55e5cfc2f3560bdc9333d624f24cdd6d4340fd7a17 AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app/src

COPY --from=deps /opt/venv /opt/venv

WORKDIR /app
# src/ is what runs; migrations/ and alembic.ini are what the release job runs.
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini

# The attachment mirror writes here, so the app user must own it.
RUN useradd --create-home --uid 10001 girvak \
    && mkdir -p /app/media \
    && chown -R girvak:girvak /app/media
USER girvak

EXPOSE 8000

# --proxy-headers: nginx is in front, and the rate limiter must see the real
# client address rather than the proxy's.
# Migrations are NOT run here: two starting containers would race. They are a
# release step (docs/operations/deployment.md).
CMD ["uvicorn", "girvak.main:create_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
