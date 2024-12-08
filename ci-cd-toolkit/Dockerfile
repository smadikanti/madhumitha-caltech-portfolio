# ---------- builder ----------
FROM python:3.12-slim AS builder

WORKDIR /build

COPY app/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

COPY app/ ./app/

RUN pip install --no-cache-dir pytest && \
    PYTHONPATH=/install/lib/python3.12/site-packages python -m pytest app/tests/ -q --no-header

# ---------- production ----------
FROM python:3.12-slim AS production

RUN groupadd -r appuser && useradd -r -g appuser -s /sbin/nologin appuser

COPY --from=builder /install /usr/local

WORKDIR /app
COPY app/ ./app/

RUN chown -R appuser:appuser /app

USER appuser

ENV PYTHONUNBUFFERED=1 \
    PORT=8000

EXPOSE ${PORT}

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/health')"

ENTRYPOINT ["gunicorn", "app.main:app", \
    "--bind", "0.0.0.0:8000", \
    "--workers", "4", \
    "--access-logfile", "-"]
