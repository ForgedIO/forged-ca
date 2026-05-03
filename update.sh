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
    PRE_PULL_HEAD="$(git -C "${SCRIPT_DIR}" rev-parse HEAD)"
    git -C "${SCRIPT_DIR}" pull --ff-only origin main
    POST_PULL_HEAD="$(git -C "${SCRIPT_DIR}" rev-parse HEAD)"
    # Re-exec ourselves if the pull advanced HEAD. Bash holds the script
    # in memory while it runs, so changes to update.sh further down in
    # this very file would otherwise sit on disk un-executed until the
    # admin runs the script a second time. UPDATE_REEXECED guards against
    # an infinite re-exec loop if something goes wrong with the rev-parse.
    if [[ "${PRE_PULL_HEAD}" != "${POST_PULL_HEAD}" && -z "${UPDATE_REEXECED:-}" ]]; then
        echo "==> update.sh itself changed (${PRE_PULL_HEAD:0:7} -> ${POST_PULL_HEAD:0:7}); re-execing with new version"
        export UPDATE_REEXECED=1
        exec bash "${BASH_SOURCE[0]}" "$@"
    fi
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

# ---------------------------------------------------------------------------
# Re-encrypt any plaintext CA keys left over from early slice 2A
#
# Idempotent: a no-op on boxes whose keys are already password-protected.
# Must run as APP_USER because the key files live in /etc/step-ca/ (owned by
# step-ca:step-ca) with mode 0640 and SGID — forgedca writes through group.
# ---------------------------------------------------------------------------
echo "==> Ensuring CA signing keys are encrypted at rest..."
sudo -u "${APP_USER}" bash -c "cd ${APP_HOME} && \
    DJANGO_SETTINGS_MODULE=forgedca.settings.production \
    ${PYTHON} manage.py encrypt_ca_keys"

# Re-render ca.json from current model state so newly-added config (ACME
# provisioner today, templates in later slices) reaches step-ca on every
# deploy without the admin having to click Save.
echo "==> Re-rendering /etc/step-ca/ca.json..."
sudo -u "${APP_USER}" bash -c "cd ${APP_HOME} && \
    DJANGO_SETTINGS_MODULE=forgedca.settings.production \
    ${PYTHON} manage.py render_ca_json"

# ---------------------------------------------------------------------------
# Heal CA-directory permissions
#
# step-cli writes *.crt at mode 0600 regardless of umask, which blocks
# step-ca (running as the step-ca user, group step-ca) from opening the
# chain on startup. Fix in-place on existing boxes and set a default ACL
# so future drops inherit group-read.
# ---------------------------------------------------------------------------
STEP_CA_CONFIG_DIR="/etc/step-ca"
STEP_CA_USER="step-ca"
if [[ -d "${STEP_CA_CONFIG_DIR}/certs" ]]; then
    chmod 0640 "${STEP_CA_CONFIG_DIR}/certs"/*.crt     2>/dev/null || true
    chmod 0640 "${STEP_CA_CONFIG_DIR}/secrets"/*       2>/dev/null || true
    if ! command -v setfacl &>/dev/null; then
        if   command -v apt-get &>/dev/null; then DEBIAN_FRONTEND=noninteractive apt-get install -y -qq acl >/dev/null 2>&1 || true
        elif command -v dnf     &>/dev/null; then dnf install -y acl >/dev/null 2>&1 || true
        elif command -v zypper  &>/dev/null; then zypper --non-interactive install -y acl >/dev/null 2>&1 || true
        fi
    fi
    if command -v setfacl &>/dev/null; then
        setfacl -m    "g:${STEP_CA_USER}:rX" "${STEP_CA_CONFIG_DIR}/certs" "${STEP_CA_CONFIG_DIR}/secrets" 2>/dev/null || true
        setfacl -d -m "g:${STEP_CA_USER}:r"  "${STEP_CA_CONFIG_DIR}/certs" "${STEP_CA_CONFIG_DIR}/secrets" 2>/dev/null || true
    fi
fi

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
# Re-render nginx config from the synced template
#
# install.sh writes the rendered nginx config once at install time. After
# that, subsequent template changes (header tweaks, new locations) need to
# be re-rendered into the live nginx config — otherwise the template in
# /opt/forgedca/deploy/ silently diverges from what nginx actually serves.
# Read the current PORT out of the existing rendered config so we don't
# need to persist it elsewhere; default to 8443 if for any reason the
# existing config is missing or unreadable.
# ---------------------------------------------------------------------------
echo "==> Re-rendering nginx config from template..."
NGINX_CONF_FILE="/etc/nginx/conf.d/forgedca.conf"
[[ -f /etc/nginx/sites-available/forgedca ]] && NGINX_CONF_FILE="/etc/nginx/sites-available/forgedca"
PORT=""
if [[ -f "${NGINX_CONF_FILE}" ]]; then
    PORT="$(grep -oE 'listen[[:space:]]+[0-9]+' "${NGINX_CONF_FILE}" | head -1 | awk '{print $NF}')"
fi
PORT="${PORT:-8443}"

NGINX_TMP="${NGINX_CONF_FILE}.new"
sed -e "s|{{ WEB_PORT }}|${PORT}|g" \
    "${APP_HOME}/deploy/nginx.conf.template" > "${NGINX_TMP}"
if grep -q '{{' "${NGINX_TMP}"; then
    rm -f "${NGINX_TMP}"
    echo "    ERROR: unrendered placeholders remain in nginx template; left existing config alone." >&2
    exit 1
fi

# Atomic swap, then validate against the live nginx config tree.
NGINX_BACKUP="${NGINX_CONF_FILE}.bak"
cp -a "${NGINX_CONF_FILE}" "${NGINX_BACKUP}" 2>/dev/null || true
mv "${NGINX_TMP}" "${NGINX_CONF_FILE}"
if nginx -t >/dev/null 2>&1; then
    if systemctl is-active nginx &>/dev/null; then
        nginx -s reload
    fi
    rm -f "${NGINX_BACKUP}"
    echo "    Nginx config re-rendered (port ${PORT}) and reloaded."
else
    if [[ -f "${NGINX_BACKUP}" ]]; then
        mv "${NGINX_BACKUP}" "${NGINX_CONF_FILE}"
        echo "    ERROR: re-rendered nginx config failed nginx -t; reverted to previous config." >&2
    else
        echo "    ERROR: re-rendered nginx config failed nginx -t and no backup was made." >&2
    fi
    nginx -t >&2 || true
    exit 1
fi

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

# ---------------------------------------------------------------------------
# Mirror the CA passphrase into the Django .env as FORGEDCA_CA_PASSWORD
#
# step-ca reads the passphrase from /etc/step-ca/secrets/password.txt
# directly. Django code can read the same file via apps.ca.password_file,
# but an env-var mirror is cheaper to access from management commands and
# matches the service-account + env-var pattern an auditor expects. Only
# written when missing — never overwrites an existing value.
# ---------------------------------------------------------------------------
CA_PW_FILE="/etc/step-ca/secrets/password.txt"
ENV_FILE="${APP_HOME}/.env"
if [[ -f "${CA_PW_FILE}" && -f "${ENV_FILE}" ]]; then
    if ! grep -q "^FORGEDCA_CA_PASSWORD=" "${ENV_FILE}"; then
        CA_PW_VAL="$(cat "${CA_PW_FILE}")"
        {
            echo ""
            echo "# CA signing-key passphrase — mirror of /etc/step-ca/secrets/password.txt"
            echo "FORGEDCA_CA_PASSWORD=${CA_PW_VAL}"
        } >> "${ENV_FILE}"
        chmod 600 "${ENV_FILE}"
        chown "${APP_USER}:${APP_USER}" "${ENV_FILE}"
        echo "==> Mirrored CA passphrase into ${ENV_FILE}"
    fi
fi

echo "==> Restarting services..."
systemctl restart forgedca-gunicorn forgedca-celery
# step-ca needs a full restart to pick up the new --password-file arg.
# Reload (SIGHUP) only rereads ca.json, not the ExecStart flags.
if systemctl is-active step-ca &>/dev/null; then
    systemctl restart step-ca
fi

echo ""
echo "ForgedCA updated successfully."
systemctl is-active forgedca-gunicorn forgedca-celery
