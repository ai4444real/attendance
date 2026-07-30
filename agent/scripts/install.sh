#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Eseguire con sudo: sudo ./scripts/install.sh" >&2
  exit 1
fi

install -d -o ubuntu -g ubuntu /var/lib/rebekko-agent
python3 -m venv /opt/rebekko-agent/.venv
/opt/rebekko-agent/.venv/bin/pip install --upgrade pip
/opt/rebekko-agent/.venv/bin/pip install -r /opt/rebekko-agent/requirements.txt

if [[ ! -f /etc/rebekko-agent.env ]]; then
  install -m 600 /opt/rebekko-agent/.env.example /etc/rebekko-agent.env
fi
install -m 644 /opt/rebekko-agent/infra/rebekko-agent.service \
  /etc/systemd/system/rebekko-agent.service

systemctl daemon-reload
systemctl enable --now rebekko-agent
systemctl status rebekko-agent --no-pager
