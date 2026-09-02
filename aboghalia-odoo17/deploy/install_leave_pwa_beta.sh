#!/usr/bin/env bash
# Install / refresh Leaves PWA beta proxy on port 8095 (not 8070/8071)
set -euo pipefail

ROOT="${1:-/odoo17-v2-beta}"
PORT="${LEAVE_PWA_PORT:-8095}"
SERVICE_SRC="${ROOT}/deploy/leave-pwa-beta.service"
SERVICE_DST="/etc/systemd/system/leave-pwa-beta.service"

if [[ ! -f "$SERVICE_SRC" ]]; then
  echo "Missing $SERVICE_SRC"
  exit 1
fi
if [[ ! -f "${ROOT}/scripts/leave_pwa_proxy.py" ]]; then
  echo "Missing ${ROOT}/scripts/leave_pwa_proxy.py"
  exit 1
fi

chmod +x "${ROOT}/scripts/leave_pwa_proxy.py"
cp "$SERVICE_SRC" "$SERVICE_DST"
# Point WorkingDirectory / ExecStart at this checkout
sed -i "s|/odoo17-v2-beta|${ROOT}|g" "$SERVICE_DST"
# Ensure port in unit file
sed -i "s|LEAVE_PWA_PORT=.*|LEAVE_PWA_PORT=${PORT}|g" "$SERVICE_DST"

systemctl daemon-reload
systemctl enable leave-pwa-beta
systemctl restart leave-pwa-beta
sleep 2
if ! systemctl is-active --quiet leave-pwa-beta; then
  echo "leave-pwa-beta failed to start — journal:"
  journalctl -u leave-pwa-beta -n 30 --no-pager || true
  exit 1
fi
systemctl --no-pager --full status leave-pwa-beta | head -n 20

# Open firewall if ufw is active
if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "Status: active"; then
  ufw allow "${PORT}/tcp" || true
fi

echo "==> Leaves PWA beta HTTPS: https://aboghaliaoffice.com:8443/  (nginx → 127.0.0.1:${PORT} → Odoo :8070)"
echo "==> Direct proxy (localhost only): http://127.0.0.1:${PORT}/"
