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

echo "==> Regenerating any model migrations the repo is missing..."
# Defensive: if the developer changed a model but forgot to ship the
# migration, or if a migration file drifts from the model, makemigrations
# fills the gap locally so `migrate` below has something to apply. On a
# clean repo this is a no-op ("No changes detected").
#
# Run from ${APP_HOME} — Python otherwise puts cwd on sys.path[0] and
# can resolve `apps.core` from the source checkout (e.g. /home/cday/forged-ca/)
# instead of the deployed copy, which causes makemigrations to try to
# write to a directory the forgedca user can't write to.
sudo -u "${APP_USER}" bash -c "cd ${APP_HOME} && \
    DJANGO_SETTINGS_MODULE=forgedca.settings.production \
    ${PYTHON} manage.py makemigrations --noinput"

echo "==> Running database migrations..."
sudo -u "${APP_USER}" bash -c "cd ${APP_HOME} && \
    DJANGO_SETTINGS_MODULE=forgedca.settings.production \
    ${PYTHON} manage.py migrate --noinput"

if ! command -v npm &>/dev/null; then
    echo "    ERROR: npm not found on PATH." >&2
    exit 1
fi
echo "==> Installing frontend dependencies..."
if ! sudo -u "${APP_USER}" bash -c "cd ${APP_HOME} && npm install"; then
    echo "    ERROR: npm install failed. Fix the errors above and re-run update.sh." >&2
    exit 1
fi
echo "==> Building Tailwind CSS..."
if ! sudo -u "${APP_USER}" bash -c "cd ${APP_HOME} && npm run build:css"; then
    echo "    ERROR: npm run build:css failed. The UI would render unstyled." >&2
    exit 1
fi
if [[ ! -s "${APP_HOME}/static/css/app.css" ]]; then
    echo "    ERROR: ${APP_HOME}/static/css/app.css is missing or empty after build." >&2
    exit 1
fi
echo "    Tailwind CSS built: $(wc -c < "${APP_HOME}/static/css/app.css") bytes"

echo "==> Collecting static files..."
sudo -u "${APP_USER}" bash -c "cd ${APP_HOME} && \
    DJANGO_SETTINGS_MODULE=forgedca.settings.production \
    ${PYTHON} manage.py collectstatic --noinput" 2>&1 | tail -3

# ---------------------------------------------------------------------------
# Refresh systemd units if templates changed
# ---------------------------------------------------------------------------
echo "==> Refreshing systemd units..."
cp "${APP_HOME}/deploy/gunicorn.service.template" /etc/systemd/system/forgedca-gunicorn.service
cp "${APP_HOME}/deploy/celery.service.template"   /etc/systemd/system/forgedca-celery.service
cp "${APP_HOME}/deploy/step-ca.service.template"  /etc/systemd/system/step-ca.service
systemctl daemon-reload

# ---------------------------------------------------------------------------
# Refresh sudoers drop-ins
#
# Slice 2A widened the step-ca sudoers grant (added enable/disable/is-active/
# is-enabled). Any box whose install.sh pre-dates that change needs the drop-in
# rewritten. Writing via a temp file + visudo -c keeps a syntax error from
# wiping sudo access; we only move it into place if it validates.
# ---------------------------------------------------------------------------
echo "==> Refreshing sudoers drop-ins..."
refresh_sudoers() {
    local name="$1"
    local tmp="/etc/sudoers.d/.${name}.new"
    cat > "${tmp}"
    chmod 440 "${tmp}"
    if visudo -cf "${tmp}" >/dev/null; then
        mv "${tmp}" "/etc/sudoers.d/${name}"
    else
        rm -f "${tmp}"
        echo "    ERROR: /etc/sudoers.d/${name} would have been invalid — left existing file alone." >&2
        return 1
    fi
}

NGINX_CONF_FILE="/etc/nginx/conf.d/forgedca.conf"
[[ -f /etc/nginx/sites-available/forgedca ]] && NGINX_CONF_FILE="/etc/nginx/sites-available/forgedca"

refresh_sudoers forgedca-nginx <<EOF
${APP_USER} ALL=(ALL) NOPASSWD: /usr/sbin/nginx -s reload
${APP_USER} ALL=(ALL) NOPASSWD: /usr/sbin/nginx -t
${APP_USER} ALL=(ALL) NOPASSWD: /usr/bin/tee ${NGINX_CONF_FILE}
${APP_USER} ALL=(ALL) NOPASSWD: /usr/bin/tee ${APP_HOME}/deploy/acme-challenge.conf
EOF

refresh_sudoers forgedca-stepca <<EOF
${APP_USER} ALL=(ALL) NOPASSWD: /bin/systemctl start step-ca
${APP_USER} ALL=(ALL) NOPASSWD: /bin/systemctl stop step-ca
${APP_USER} ALL=(ALL) NOPASSWD: /bin/systemctl restart step-ca
${APP_USER} ALL=(ALL) NOPASSWD: /bin/systemctl reload step-ca
${APP_USER} ALL=(ALL) NOPASSWD: /bin/systemctl status step-ca
${APP_USER} ALL=(ALL) NOPASSWD: /bin/systemctl enable step-ca
${APP_USER} ALL=(ALL) NOPASSWD: /bin/systemctl disable step-ca
${APP_USER} ALL=(ALL) NOPASSWD: /bin/systemctl is-active step-ca
${APP_USER} ALL=(ALL) NOPASSWD: /bin/systemctl is-enabled step-ca
${APP_USER} ALL=(ALL) NOPASSWD: /usr/bin/systemctl start step-ca
${APP_USER} ALL=(ALL) NOPASSWD: /usr/bin/systemctl stop step-ca
${APP_USER} ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart step-ca
${APP_USER} ALL=(ALL) NOPASSWD: /usr/bin/systemctl reload step-ca
${APP_USER} ALL=(ALL) NOPASSWD: /usr/bin/systemctl status step-ca
${APP_USER} ALL=(ALL) NOPASSWD: /usr/bin/systemctl enable step-ca
${APP_USER} ALL=(ALL) NOPASSWD: /usr/bin/systemctl disable step-ca
${APP_USER} ALL=(ALL) NOPASSWD: /usr/bin/systemctl is-active step-ca
${APP_USER} ALL=(ALL) NOPASSWD: /usr/bin/systemctl is-enabled step-ca
${APP_USER} ALL=(ALL) NOPASSWD: /bin/journalctl -u step-ca --no-pager -n 30 --output=short-iso
${APP_USER} ALL=(ALL) NOPASSWD: /usr/bin/journalctl -u step-ca --no-pager -n 30 --output=short-iso
EOF

echo "==> Restarting services..."
systemctl restart forgedca-gunicorn forgedca-celery
# step-ca only restarts if it was already running
if systemctl is-active step-ca &>/dev/null; then
    systemctl reload step-ca 2>/dev/null || systemctl restart step-ca
fi

echo ""
echo "ForgedCA updated successfully."
systemctl is-active forgedca-gunicorn forgedca-celery
