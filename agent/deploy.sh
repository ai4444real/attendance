#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REBEKKO_AGENT_SOURCE_REPO:-/home/ubuntu/src/rebekko-webapps}"
INSTALL_DIR="${REBEKKO_AGENT_INSTALL_DIR:-/opt/rebekko-agent}"
SERVICE_NAME="${REBEKKO_AGENT_SERVICE:-rebekko-agent}"

cd "$REPO_DIR"
git pull --ff-only origin main

sudo mkdir -p "$INSTALL_DIR"
sudo cp -a agent/. "$INSTALL_DIR/"
sudo systemctl restart "$SERVICE_NAME"
sudo systemctl status "$SERVICE_NAME" --no-pager
