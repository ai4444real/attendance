#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${PROJECT_ROOT}/.env"
SERVICE_NAME="${REBEKKO_SERVICE_NAME:-rebekko-webapps}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "[auth] missing ${ENV_FILE}" >&2
  exit 1
fi

if grep -q '^AUTH_ENABLED=' "${ENV_FILE}"; then
  sed -i 's/^AUTH_ENABLED=.*/AUTH_ENABLED=false/' "${ENV_FILE}"
else
  printf '\nAUTH_ENABLED=false\n' >> "${ENV_FILE}"
fi

echo "[auth] AUTH_ENABLED=false"
sudo systemctl restart "${SERVICE_NAME}"
echo "[auth] restarted ${SERVICE_NAME}"
