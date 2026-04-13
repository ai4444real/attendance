#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/rebekko/webapps"
VENV_DIR="$APP_DIR/.venv"
SERVICE_NAME="rebekko-webapps"

cd "$APP_DIR"
git pull origin main
source "$VENV_DIR/bin/activate"
pip install -r requirements.txt
sudo systemctl restart "$SERVICE_NAME"
sudo systemctl --no-pager --full status "$SERVICE_NAME"
