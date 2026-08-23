#!/usr/bin/env bash
# Smoke-test a deployed API Monitoring backend (no credentials required).
set -euo pipefail

BACKEND_URL="${1:-}"
if [[ -z "${BACKEND_URL}" ]]; then
  echo "Usage: $0 <BACKEND_URL>"
  echo "Example: $0 https://api-monitoring-backend.onrender.com"
  exit 1
fi

BACKEND_URL="${BACKEND_URL%/}"

check() {
  local path="$1"
  local expected="${2:-200}"
  local url="${BACKEND_URL}${path}"
  local status
  status="$(curl -s -o /tmp/smoke-body.txt -w "%{http_code}" "${url}")"
  if [[ "${status}" != "${expected}" ]]; then
    echo "FAIL ${path} expected ${expected} got ${status}"
    cat /tmp/smoke-body.txt
    exit 1
  fi
  echo "OK   ${path} (${status})"
}

check "/health/live" 200
check "/health/ready" 200
check "/docs" 200
check "/metrics" 200

echo "Smoke test passed for ${BACKEND_URL}"
