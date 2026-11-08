FROM python:3.12-slim-bookworm AS builder

WORKDIR /build
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir uv==0.12.8 \
    && uv sync --locked --no-dev --extra api --no-editable

FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    HOST=0.0.0.0 \
    PORT=8080
WORKDIR /app
RUN groupadd --gid 10001 terramind \
    && useradd --uid 10001 --gid 10001 --no-create-home terramind
COPY --from=builder /build/.venv /opt/venv
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2).read()"]
ENTRYPOINT ["python", "-m", "terramind.api"]
