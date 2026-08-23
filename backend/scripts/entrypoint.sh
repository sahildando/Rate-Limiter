#!/bin/sh
# Assemble connection URLs from ECS/Secrets Manager injected env vars when needed.
set -e

if [ -z "${DATABASE_URL:-}" ] && [ -n "${DB_HOST:-}" ]; then
  export DATABASE_URL="postgresql+asyncpg://${DB_USERNAME}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT:-5432}/${DB_NAME:-monitoring}"
fi

if [ -z "${REDIS_URL:-}" ] && [ -n "${REDIS_HOST:-}" ]; then
  export REDIS_URL="redis://${REDIS_HOST}:${REDIS_PORT:-6379}/${REDIS_DB:-0}"
fi

if [ -z "${CELERY_BROKER_URL:-}" ]; then
  export CELERY_BROKER_URL="${REDIS_URL}"
fi

if [ -z "${CELERY_RESULT_BACKEND:-}" ]; then
  export CELERY_RESULT_BACKEND="${REDIS_URL}"
fi

exec "$@"
