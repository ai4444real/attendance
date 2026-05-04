#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/rebekko/webapps"
VENV_DIR="$APP_DIR/.venv"
SERVICE_NAME="rebekko-webapps"
HEALTH_URL="https://rebekko.pnlevolution.com/health"

cd "$APP_DIR"

echo "[deploy] repo: $APP_DIR"
echo "[deploy] pull latest main"
git pull --ff-only origin main

echo "[deploy] install/update dependencies in venv"
"$VENV_DIR/bin/pip" install -r requirements.txt

echo "[deploy] restart service: $SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

echo "[deploy] service status"
sudo systemctl --no-pager --full status "$SERVICE_NAME"

echo "[deploy] health check"
curl --fail --silent --show-error "$HEALTH_URL"
echo

echo "[deploy] done"
