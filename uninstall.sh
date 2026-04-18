#!/usr/bin/env bash
# ForgedCA uninstaller
# Usage: sudo ./uninstall.sh [--keep-data]
set -euo pipefail

APP_USER="forgedca"
APP_HOME="/opt/forgedca"
LOG_DIR="/var/log/forgedca"
STEP_CA_USER="step-ca"
STEP_CA_CONFIG_DIR="/etc/step-ca"
STEP_CA_DATA_DIR="/var/lib/step-ca"

KEEP_DATA=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --keep-data) KEEP_DATA=true; shift ;;
        --help|-h)
            echo "Usage: sudo $0 [--keep-data]"
            echo ""
            echo "  --keep-data   Remove services and packages but keep /opt/forgedca,"
            echo "                /etc/step-ca, /var/lib/step-ca, DB contents, and logs"
            exit 0
            ;;
        *) echo "ERROR: Unknown argument: $1" >&2; exit 1 ;;
    esac
done

if [[ "${EUID}" -ne 0 ]]; then
    echo "ERROR: This script must be run as root (use sudo)." >&2
    exit 1
fi

echo ""
echo "============================================================"
echo "  ForgedCA Uninstaller"
echo "============================================================"
echo ""
if [[ "${KEEP_DATA}" == "true" ]]; then
    echo "  Mode: Remove services only (data preserved)"
else
    echo "  Mode: Full removal (services + all data, including CA keys)"
    echo ""
    echo "  WARNING: this will permanently delete:"
    echo "    - ${APP_HOME} (Django app, venv, .env, TLS certs)"
    echo "    - ${STEP_CA_CONFIG_DIR} (step-ca config and CA key material)"
    echo "    - ${STEP_CA_DATA_DIR} (step-ca runtime state)"
    echo "    - Postgres databases 'forgedca' and 'step_ca'"
    echo "    - Log directories"
    echo "    - System users '${APP_USER}' and '${STEP_CA_USER}'"
    echo ""
    echo "  If you are using offline/air-gapped Root mode, BACK UP ${STEP_CA_CONFIG_DIR}"
    echo "  NOW — the CA keys cannot be recovered once removed."
fi
echo ""
read -rp "  Type 'yes' to confirm: " CONFIRM
if [[ "${CONFIRM}" != "yes" ]]; then
    echo "Aborted."
    exit 0
fi
echo ""

echo "==> Stopping services..."
for SVC in forgedca-gunicorn forgedca-celery step-ca; do
    systemctl is-active "${SVC}" &>/dev/null && systemctl stop "${SVC}"
    systemctl is-enabled "${SVC}" &>/dev/null && systemctl disable "${SVC}"
    rm -f "/etc/systemd/system/${SVC}.service"
done
systemctl daemon-reload

echo "==> Removing Nginx configuration..."
rm -f /etc/nginx/sites-enabled/forgedca /etc/nginx/sites-available/forgedca /etc/nginx/conf.d/forgedca.conf
rm -f /etc/sudoers.d/forgedca-nginx
if systemctl is-active nginx &>/dev/null; then
    nginx -t 2>/dev/null && systemctl reload nginx && echo "    Nginx reloaded."
fi

echo "==> Removing runtime directory..."
rm -rf /run/forgedca

if [[ "${KEEP_DATA}" == "false" ]]; then
    echo "==> Dropping Postgres databases..."
    su - postgres -c "psql -c 'DROP DATABASE IF EXISTS forgedca;'" 2>/dev/null || true
    su - postgres -c "psql -c 'DROP DATABASE IF EXISTS step_ca;'"  2>/dev/null || true
    su - postgres -c "psql -c 'DROP ROLE IF EXISTS forgedca;'"     2>/dev/null || true
    su - postgres -c "psql -c 'DROP ROLE IF EXISTS step_ca;'"      2>/dev/null || true

    echo "==> Removing application data..."
    rm -rf "${APP_HOME}" "${STEP_CA_CONFIG_DIR}" "${STEP_CA_DATA_DIR}" "${LOG_DIR}" /var/log/step-ca

    echo "==> Removing system users..."
    id "${APP_USER}"    &>/dev/null && userdel "${APP_USER}"
    id "${STEP_CA_USER}" &>/dev/null && userdel "${STEP_CA_USER}"
else
    echo "==> Data preserved:"
    echo "    ${APP_HOME}"
    echo "    ${STEP_CA_CONFIG_DIR}"
    echo "    ${STEP_CA_DATA_DIR}"
    echo "    Postgres databases forgedca, step_ca"
fi

echo ""
echo "============================================================"
echo "  ForgedCA has been uninstalled."
if [[ "${KEEP_DATA}" == "true" ]]; then
    echo "  Data preserved. To remove it, run: sudo $0 (without --keep-data)"
fi
echo "============================================================"
echo ""
