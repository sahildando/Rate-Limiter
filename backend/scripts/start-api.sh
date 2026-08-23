#!/bin/sh
set -e

PORT="${PORT:-8000}"
WORKERS="${WEB_CONCURRENCY:-2}"

exec gunicorn app.main:app \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind "0.0.0.0:${PORT}" \
  --workers "${WORKERS}" \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
