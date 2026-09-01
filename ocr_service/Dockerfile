FROM dhi.io/uv:0-debian13 AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON=3.14

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN ["uv", "sync", "--frozen", "--no-install-project"]

COPY main.py ./
RUN ["uv", "sync", "--frozen"]

FROM python:3.14-slim AS prod

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      tesseract-ocr \
      tesseract-ocr-eng \
 && rm -rf /var/lib/apt/lists/*

RUN groupadd -g 30500 ocr && useradd -u 30500 -g ocr -d /app -M ocr

WORKDIR /app

COPY --from=builder /app/.venv/lib /app/.venv/lib
COPY --from=builder /app/main.py /app/main.py

USER 30500:30500

ENV PYTHONPATH=/app/.venv/lib/python3.14/site-packages:/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 9000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:9000/health')"

ENTRYPOINT ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9000"]
