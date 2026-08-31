FROM dhi.io/uv:0-debian13 AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON=3.14

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN ["uv", "sync", "--frozen", "--no-install-project"]

COPY app/ ./app/
RUN ["uv", "sync", "--frozen"]

FROM python:3.14-slim AS prod

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      tesseract-ocr \
      tesseract-ocr-eng \
 && rm -rf /var/lib/apt/lists/*

RUN groupadd -g 30000 app && useradd -u 30000 -g app -d /app -M app

WORKDIR /app

COPY --from=builder /app/.venv/lib /app/.venv/lib
COPY --from=builder /app/app /app/app

USER 30000:30000

ENV PYTHONPATH=/app/.venv/lib/python3.14/site-packages:/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')"

ENTRYPOINT ["python3", "-m", "app"]
