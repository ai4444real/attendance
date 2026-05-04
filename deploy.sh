#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/rebekko/webapps"
VENV_DIR="$APP_DIR/.venv"
SERVICE_NAME="rebekko-webapps"
LOCAL_HEALTH_URL="http://127.0.0.1:8080/health"
HEALTH_URL="https://rebekko.pnlevolution.com/health"
LOCAL_HEALTH_ATTEMPTS=15
LOCAL_HEALTH_SLEEP_SECONDS=1

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

echo "[deploy] wait for local health check"
for attempt in $(seq 1 "$LOCAL_HEALTH_ATTEMPTS"); do
    if curl --fail --silent --show-error "$LOCAL_HEALTH_URL" >/dev/null; then
        echo "[deploy] local health ok on attempt $attempt/$LOCAL_HEALTH_ATTEMPTS"
        break
    fi

    if [[ "$attempt" -eq "$LOCAL_HEALTH_ATTEMPTS" ]]; then
        echo "[deploy] local health failed after $LOCAL_HEALTH_ATTEMPTS attempts"
        exit 1
    fi

    sleep "$LOCAL_HEALTH_SLEEP_SECONDS"
done

echo "[deploy] public health check"
curl --fail --silent --show-error "$HEALTH_URL"
echo

echo "[deploy] done"
