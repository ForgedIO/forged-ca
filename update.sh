#!/usr/bin/env bash
# ForgedCA updater
# Usage: sudo ./update.sh
#
# Pulls the latest code from the repo you're running this from, syncs files
# into /opt/forgedca/, refreshes dependencies, runs migrations, rebuilds
# Tailwind CSS, and restarts the services. Preserves .env, certs, DB, and
# step-ca state.
set -euo pipefail

APP_USER="forgedca"
APP_HOME="/opt/forgedca"
VENV="${APP_HOME}/venv"
PYTHON="${VENV}/bin/python"
PIP="${VENV}/bin/pip"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ "${EUID}" -ne 0 ]]; then
    echo "ERROR: update.sh must be run as root (sudo ./update.sh)" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Self-pull: if this script is inside a git checkout, fetch the latest commit
# ---------------------------------------------------------------------------
if [[ -d "${SCRIPT_DIR}/.git" ]]; then
    echo "==> git pull origin main"
    git -C "${SCRIPT_DIR}" fetch --quiet origin
    git -C "${SCRIPT_DIR}" pull --ff-only origin main
else
    echo "==> Not a git checkout — skipping git pull (assuming code already updated)"
fi

# ---------------------------------------------------------------------------
# Sync application files into /opt/forgedca/
# ---------------------------------------------------------------------------
echo "==> Syncing application files to ${APP_HOME}..."
COPY_DIRS=(apps forgedca templates static help deploy scripts tests)
for d in "${COPY_DIRS[@]}"; do
    if [[ -d "${SCRIPT_DIR}/${d}" ]]; then
        rsync -a --delete "${SCRIPT_DIR}/${d}/" "${APP_HOME}/${d}/"
        chown -R "${APP_USER}:${APP_USER}" "${APP_HOME}/${d}"
    fi
done

for f in manage.py requirements.txt package.json package-lock.json tailwind.config.js postcss.config.js; do
    if [[ -f "${SCRIPT_DIR}/${f}" ]]; then
        cp "${SCRIPT_DIR}/${f}" "${APP_HOME}/${f}"
        chown "${APP_USER}:${APP_USER}" "${APP_HOME}/${f}"
    fi
done

chown -R "${APP_USER}:${APP_USER}" "${VENV}"

# ---------------------------------------------------------------------------
# Dependencies + migrations + static
# ---------------------------------------------------------------------------
echo "==> Installing Python dependencies..."
sudo -u "${APP_USER}" "${PIP}" install -q -r "${APP_HOME}/requirements.txt"

echo "==> Running database migrations..."
sudo -u "${APP_USER}" \
    DJANGO_SETTINGS_MODULE=forgedca.settings.production \
    "${PYTHON}" "${APP_HOME}/manage.py" migrate --noinput

if command -v npm &>/dev/null; then
    echo "==> Installing frontend dependencies..."
    sudo -u "${APP_USER}" bash -c "cd ${APP_HOME} && npm install 2>&1 | tail -1" || true
    echo "==> Building Tailwind CSS..."
    sudo -u "${APP_USER}" bash -c "cd ${APP_HOME} && npm run build:css 2>&1 | tail -1" || true
fi

echo "==> Collecting static files..."
sudo -u "${APP_USER}" \
    DJANGO_SETTINGS_MODULE=forgedca.settings.production \
    "${PYTHON}" "${APP_HOME}/manage.py" collectstatic --noinput 2>&1 | tail -3

# ---------------------------------------------------------------------------
# Refresh systemd units if templates changed
# ---------------------------------------------------------------------------
echo "==> Refreshing systemd units..."
cp "${APP_HOME}/deploy/gunicorn.service.template" /etc/systemd/system/forgedca-gunicorn.service
cp "${APP_HOME}/deploy/celery.service.template"   /etc/systemd/system/forgedca-celery.service
cp "${APP_HOME}/deploy/step-ca.service.template"  /etc/systemd/system/step-ca.service
systemctl daemon-reload

echo "==> Restarting services..."
systemctl restart forgedca-gunicorn forgedca-celery
# step-ca only restarts if it was already running
if systemctl is-active step-ca &>/dev/null; then
    systemctl reload step-ca 2>/dev/null || systemctl restart step-ca
fi

echo ""
echo "ForgedCA updated successfully."
systemctl is-active forgedca-gunicorn forgedca-celery
