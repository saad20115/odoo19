#!/usr/bin/env bash
# One-time server setup for employee portal beta (port 8072, DB BetaEmployeeDB1)
set -euo pipefail

ROOT="${1:-/odoo17-v2-employee-beta}"
SOURCE_DB="${SOURCE_DB:-BetaDB1}"
TARGET_DB="${TARGET_DB:-BetaEmployeeDB1}"
ODOO_USER="${ODOO_USER:-odoo17-v2}"
CONF="/etc/odoo17-v2-employee-beta.conf"

echo "==> Employee portal beta setup (root=${ROOT})"

if [[ ! -d "$ROOT" ]]; then
  echo "Missing checkout at ${ROOT}. Clone the repo first."
  exit 1
fi

mkdir -p /var/lib/odoo-employee-beta /var/log/odoo
chown -R "${ODOO_USER}:${ODOO_USER}" /var/lib/odoo-employee-beta /var/log/odoo

if [[ ! -f "$CONF" ]]; then
  if [[ -f /etc/odoo17-v2-beta.conf ]]; then
    cp /etc/odoo17-v2-beta.conf "$CONF"
    sed -i 's/http_port = .*/http_port = 8072/' "$CONF"
    sed -i 's|^dbfilter = .*|dbfilter = ^BetaEmployeeDB1$|' "$CONF"
    sed -i 's|^data_dir = .*|data_dir = /var/lib/odoo-employee-beta|' "$CONF"
    sed -i 's|^logfile = .*|logfile = /var/log/odoo/odoo-employee-beta.log|' "$CONF"
    sed -i "s|list_db = .*|list_db = False|" "$CONF"
    sed -i "s|/odoo17-v2-beta|${ROOT}|g" "$CONF"
  else
    cp "${ROOT}/deploy/odoo-employee-beta.conf.template" "$CONF"
    echo "Edit ${CONF} with db_password and admin_passwd before continuing."
    exit 1
  fi
  chown root:"${ODOO_USER}" "$CONF"
  chmod 640 "$CONF"
fi

cp "${ROOT}/deploy/odoo-employee-beta.service" /etc/systemd/system/odoo17-v2-employee-beta-server.service
sed -i "s|/odoo17-v2-employee-beta|${ROOT}|g" /etc/systemd/system/odoo17-v2-employee-beta-server.service
systemctl daemon-reload
systemctl enable odoo17-v2-employee-beta-server

if ! sudo -u postgres psql -lqt | cut -d \| -f 1 | grep -qw "$TARGET_DB"; then
  echo "==> Creating database ${TARGET_DB}"
  sudo -u postgres createdb -O "${ODOO_USER}" "$TARGET_DB"
fi

echo "==> Fetching installed modules from ${SOURCE_DB}"
MODULES=$(sudo -u postgres psql -d "$SOURCE_DB" -Atc \
  "SELECT string_agg(name, ',' ORDER BY name) FROM ir_module_module WHERE state = 'installed' AND name != 'base';")

echo "==> Installing modules on ${TARGET_DB} (may take several minutes)..."
sudo -u "${ODOO_USER}" python3 "${ROOT}/odoo17-v2-server/odoo-bin" \
  -c "$CONF" -d "$TARGET_DB" -i "base,${MODULES}" \
  --without-demo=all --stop-after-init

echo "==> Seeding users and employees from ${SOURCE_DB}..."
sudo -u "${ODOO_USER}" python3 "${ROOT}/scripts/seed_employee_beta_db.py" \
  --source "$SOURCE_DB" --target "$TARGET_DB"

systemctl restart odoo17-v2-employee-beta-server
sleep 5
systemctl is-active odoo17-v2-employee-beta-server

if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "Status: active"; then
  ufw allow 8072/tcp || true
fi

echo "==> Employee portal beta ready:"
echo "    Odoo: http://$(hostname -I | awk '{print $1}'):8072/web"
echo "    Leave app: http://$(hostname -I | awk '{print $1}'):8072/leave"
