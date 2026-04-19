#!/usr/bin/env bash
# ForgedCA installer
# Usage: sudo ./install.sh [--port <n>]
#
# Stands up the full ForgedCA stack end-to-end: Postgres, step-ca, the Django
# web UI, Gunicorn, Celery, Redis, Nginx, and systemd units. Supports apt,
# dnf, yum, and zypper.
set -euo pipefail

APP_USER="forgedca"
APP_HOME="/opt/forgedca"
VENV="${APP_HOME}/venv"
PYTHON="${VENV}/bin/python"
PIP="${VENV}/bin/pip"
CERTS_DIR="${APP_HOME}/certs"
LOG_DIR="/var/log/forgedca"
STEP_CA_USER="step-ca"
STEP_CA_CONFIG_DIR="/etc/step-ca"
STEP_CA_DATA_DIR="/var/lib/step-ca"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_PORT=8443
PORT="${DEFAULT_PORT}"

usage() {
    echo "Usage: sudo $0 [--port <1-65535>] [--help]"
    echo ""
    echo "Options:"
    echo "  --port <n>   HTTPS port for the ForgedCA web UI (default: ${DEFAULT_PORT})"
    echo "  --help       Show this help and exit"
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --port)
            shift
            PORT="${1:-}"
            if [[ -z "${PORT}" ]]; then
                echo "ERROR: --port requires a value." >&2
                exit 1
            fi
            shift
            ;;
        --help|-h) usage ;;
        *) echo "ERROR: Unknown argument: $1" >&2; usage ;;
    esac
done

if ! [[ "${PORT}" =~ ^[0-9]+$ ]] || (( PORT < 1 || PORT > 65535 )); then
    echo "ERROR: Invalid port '${PORT}'. Must be 1-65535." >&2
    exit 1
fi

if [[ "${EUID}" -ne 0 ]]; then
    echo "ERROR: This script must be run as root (use sudo)." >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Package manager detection
# ---------------------------------------------------------------------------
echo "==> Detecting package manager..."
PKG_MANAGER=""
if command -v apt-get &>/dev/null; then PKG_MANAGER="apt"; echo "    Found: apt (Debian/Ubuntu family)"
elif command -v dnf &>/dev/null; then PKG_MANAGER="dnf"; echo "    Found: dnf (RHEL/Fedora family)"
elif command -v yum &>/dev/null; then PKG_MANAGER="yum"; echo "    Found: yum (older RHEL/CentOS family)"
elif command -v zypper &>/dev/null; then PKG_MANAGER="zypper"; echo "    Found: zypper (SUSE/openSUSE family)"
else
    echo ""
    echo "ERROR: No supported package manager found (apt-get, dnf, yum, zypper)." >&2
    echo ""
    echo "ForgedCA requires the following packages to be installed manually:"
    echo "  - Python 3.10+, python3-venv, python3-dev"
    echo "  - gcc, libldap, libsasl2, libssl, libxml2, libxmlsec1 dev headers"
    echo "  - nginx, redis, postgresql (server + client, >=13)"
    echo "  - step-ca + step CLI from smallstep.com/docs/step-ca/installation"
    echo "  - nodejs + npm"
    exit 1
fi

if [[ "${PKG_MANAGER}" == "apt" ]]; then
    REDIS_SVC="redis-server"
    POSTGRES_SVC="postgresql"
    NGINX_CONF_DIR="/etc/nginx/sites-available"
    NGINX_ENABLED_DIR="/etc/nginx/sites-enabled"
else
    REDIS_SVC="redis"
    POSTGRES_SVC="postgresql"
    NGINX_CONF_DIR="/etc/nginx/conf.d"
    NGINX_ENABLED_DIR=""
fi

# ---------------------------------------------------------------------------
# System packages
# ---------------------------------------------------------------------------
echo "==> Installing system packages..."
case "${PKG_MANAGER}" in
    apt)
        if grep -q '^deb cdrom:' /etc/apt/sources.list 2>/dev/null; then
            sed -i 's|^deb cdrom:|# deb cdrom:|g' /etc/apt/sources.list
            echo "    Disabled CD-ROM apt source."
        fi
        apt-get update -qq
        apt-get install -y \
            python3 python3-pip python3-venv python3-dev \
            gcc \
            libldap2-dev libsasl2-dev libssl-dev libxml2-dev libxmlsec1-dev libxmlsec1-openssl pkg-config \
            nginx \
            nodejs npm \
            redis-server \
            postgresql postgresql-client \
            openssl \
            curl wget rsync \
            ca-certificates gnupg 2>/dev/null || true
        ;;
    dnf|yum)
        "${PKG_MANAGER}" install -y epel-release 2>/dev/null || true
        "${PKG_MANAGER}" install -y \
            python3 python3-pip python3-devel \
            gcc \
            openldap-devel cyrus-sasl-devel openssl-devel libxml2-devel xmlsec1-devel xmlsec1-openssl-devel libtool-ltdl-devel \
            nginx \
            nodejs npm \
            redis \
            postgresql-server postgresql-contrib \
            openssl \
            curl wget rsync \
            ca-certificates gnupg2 2>/dev/null || true
        # Initialize Postgres cluster if not already done
        if [[ ! -d /var/lib/pgsql/data/base ]]; then
            postgresql-setup --initdb 2>/dev/null || /usr/bin/postgresql-setup initdb 2>/dev/null || true
        fi
        ;;
    zypper)
        zypper install -y \
            python3 python3-pip python3-devel \
            gcc \
            openldap2-devel cyrus-sasl-devel libopenssl-devel libxml2-devel xmlsec1-devel xmlsec1-openssl-devel \
            nginx \
            nodejs npm \
            redis \
            postgresql-server postgresql \
            openssl \
            curl wget rsync \
            ca-certificates gpg2 2>/dev/null || true
        if [[ ! -d /var/lib/pgsql/data/base ]]; then
            su - postgres -c "initdb -D /var/lib/pgsql/data" 2>/dev/null || true
        fi
        ;;
esac

systemctl enable --now "${POSTGRES_SVC}" 2>/dev/null || true
systemctl enable --now "${REDIS_SVC}" 2>/dev/null || true

# ---------------------------------------------------------------------------
# step-ca + step CLI installation
# ---------------------------------------------------------------------------
# Install via the official Smallstep .deb / .rpm packages. The versioned
# tarball approach is brittle: the certificates and cli repos release
# independently and not every <version> number exists in both. Packages
# put binaries on PATH, handle permissions, and are reversible through
# the distro's package manager if the admin ever wants to purge them.
STEP_VERSION="0.30.2"
ARCH="$(uname -m)"
case "${ARCH}" in
    x86_64)  STEP_DEB_ARCH="amd64";  STEP_RPM_ARCH="x86_64" ;;
    aarch64) STEP_DEB_ARCH="arm64";  STEP_RPM_ARCH="aarch64" ;;
    *)       STEP_DEB_ARCH="";       STEP_RPM_ARCH="" ;;
esac

echo "==> Installing step-ca and step CLI..."
NEED_STEP_CA="yes"; command -v step-ca &>/dev/null && NEED_STEP_CA="no"
NEED_STEP_CLI="yes"; command -v step    &>/dev/null && NEED_STEP_CLI="no"

if [[ "${NEED_STEP_CA}" == "no" && "${NEED_STEP_CLI}" == "no" ]]; then
    echo "    step-ca and step already installed: $(step-ca version 2>/dev/null | head -1); $(step version 2>/dev/null | head -1)"
else
    STEP_TMP="$(mktemp -d)"
    trap "rm -rf ${STEP_TMP}" EXIT

    case "${PKG_MANAGER}" in
        apt)
            if [[ -z "${STEP_DEB_ARCH}" ]]; then
                echo "    ERROR: unsupported architecture '${ARCH}' for step-ca .deb." >&2
                exit 1
            fi
            CERT_URL="https://github.com/smallstep/certificates/releases/download/v${STEP_VERSION}/step-ca_${STEP_VERSION}-1_${STEP_DEB_ARCH}.deb"
            CLI_URL="https://github.com/smallstep/cli/releases/download/v${STEP_VERSION}/step-cli_${STEP_VERSION}-1_${STEP_DEB_ARCH}.deb"
            if [[ "${NEED_STEP_CA}" == "yes" ]]; then
                wget -q "${CERT_URL}" -O "${STEP_TMP}/step-ca.deb" || { echo "    ERROR: failed to download ${CERT_URL}" >&2; exit 1; }
                dpkg -i "${STEP_TMP}/step-ca.deb"
            fi
            if [[ "${NEED_STEP_CLI}" == "yes" ]]; then
                wget -q "${CLI_URL}" -O "${STEP_TMP}/step-cli.deb" || { echo "    ERROR: failed to download ${CLI_URL}" >&2; exit 1; }
                dpkg -i "${STEP_TMP}/step-cli.deb"
            fi
            ;;
        dnf|yum|zypper)
            if [[ -z "${STEP_RPM_ARCH}" ]]; then
                echo "    ERROR: unsupported architecture '${ARCH}' for step-ca .rpm." >&2
                exit 1
            fi
            CERT_URL="https://github.com/smallstep/certificates/releases/download/v${STEP_VERSION}/step-ca-${STEP_VERSION}-1.${STEP_RPM_ARCH}.rpm"
            CLI_URL="https://github.com/smallstep/cli/releases/download/v${STEP_VERSION}/step-cli-${STEP_VERSION}-1.${STEP_RPM_ARCH}.rpm"
            INSTALL_CMD=("${PKG_MANAGER}" "install" "-y")
            [[ "${PKG_MANAGER}" == "zypper" ]] && INSTALL_CMD=(zypper --non-interactive install --allow-unsigned-rpm)
            if [[ "${NEED_STEP_CA}" == "yes" ]]; then
                "${INSTALL_CMD[@]}" "${CERT_URL}" || { echo "    ERROR: step-ca .rpm install failed (${CERT_URL})" >&2; exit 1; }
            fi
            if [[ "${NEED_STEP_CLI}" == "yes" ]]; then
                "${INSTALL_CMD[@]}" "${CLI_URL}" || { echo "    ERROR: step-cli .rpm install failed (${CLI_URL})" >&2; exit 1; }
            fi
            ;;
    esac

    rm -rf "${STEP_TMP}"
    trap - EXIT

    # Verify both binaries ended up on PATH. Bail loudly if not — the install
    # wizard's key-generation step will fail otherwise.
    command -v step-ca &>/dev/null || { echo "    ERROR: step-ca not on PATH after install." >&2; exit 1; }
    command -v step    &>/dev/null || { echo "    ERROR: step not on PATH after install." >&2; exit 1; }
    echo "    Installed: $(step-ca version 2>/dev/null | head -1); $(step version 2>/dev/null | head -1)"
fi

# ---------------------------------------------------------------------------
# System users
# ---------------------------------------------------------------------------
echo "==> Creating system user '${APP_USER}'..."
if ! id "${APP_USER}" &>/dev/null; then
    useradd --system --home "${APP_HOME}" --shell /sbin/nologin "${APP_USER}"
fi

echo "==> Creating system user '${STEP_CA_USER}'..."
if ! id "${STEP_CA_USER}" &>/dev/null; then
    useradd --system --home "${STEP_CA_DATA_DIR}" --shell /sbin/nologin "${STEP_CA_USER}"
fi

# ForgedCA user needs group-read on step-ca config (not on secrets/)
usermod -a -G "${STEP_CA_USER}" "${APP_USER}" 2>/dev/null || true

# ---------------------------------------------------------------------------
# Application directory
# ---------------------------------------------------------------------------
echo "==> Syncing application to ${APP_HOME}..."
mkdir -p "${APP_HOME}" "${LOG_DIR}" "${STEP_CA_CONFIG_DIR}" "${STEP_CA_DATA_DIR}"
rsync -a \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.env' \
    --exclude='node_modules' \
    --exclude='venv' \
    "${SCRIPT_DIR}/" "${APP_HOME}/"
chown -R "${APP_USER}:${APP_USER}" "${APP_HOME}" "${LOG_DIR}"
# /etc/step-ca/ is shared between step-ca (daemon) and forgedca (web UI) — the
# web UI needs to write ca.json, certs, and key material during the install
# wizard. SGID + group-write lets forgedca (a member of the step-ca group)
# create files there; group ownership is inherited from the directory, so
# step-ca can read what forgedca wrote.
mkdir -p "${STEP_CA_CONFIG_DIR}/certs" "${STEP_CA_CONFIG_DIR}/secrets" "${STEP_CA_CONFIG_DIR}/db"
chown -R "${STEP_CA_USER}:${STEP_CA_USER}" "${STEP_CA_CONFIG_DIR}" "${STEP_CA_DATA_DIR}"
chmod 2770 "${STEP_CA_CONFIG_DIR}" "${STEP_CA_CONFIG_DIR}/certs" "${STEP_CA_CONFIG_DIR}/secrets" "${STEP_CA_CONFIG_DIR}/db"
chmod 0700 "${STEP_CA_DATA_DIR}"

# Normalise file modes on any CA material that already exists.
# step-cli writes *.crt at 0600 regardless of umask — the step-ca daemon
# (running as step-ca, not forgedca) can't read them without group-r. Keys
# are already chmodded 0640 by keygen.py; this covers certs + password.txt
# for idempotency on re-runs.
chmod 0640 "${STEP_CA_CONFIG_DIR}/certs"/*.crt     2>/dev/null || true
chmod 0640 "${STEP_CA_CONFIG_DIR}/secrets"/*       2>/dev/null || true

# Belt-and-braces: a default ACL on certs/ + secrets/ means any new file a
# future code path (or step-cli upgrade, or an admin tinkering manually)
# drops in there inherits step-ca-group read, even if the creating process
# uses a tight umask. Requires the `acl` package; fall back silently if it
# isn't installed — the explicit chmods above remain the primary guarantee.
if ! command -v setfacl &>/dev/null; then
    case "${PKG_MANAGER}" in
        apt)       DEBIAN_FRONTEND=noninteractive apt-get install -y -qq acl >/dev/null 2>&1 || true ;;
        dnf|yum)   "${INSTALL_CMD[@]}" acl >/dev/null 2>&1 || true ;;
        zypper)    zypper --non-interactive install -y acl >/dev/null 2>&1 || true ;;
    esac
fi
if command -v setfacl &>/dev/null; then
    setfacl -m    g:${STEP_CA_USER}:rX "${STEP_CA_CONFIG_DIR}/certs" "${STEP_CA_CONFIG_DIR}/secrets" 2>/dev/null || true
    setfacl -d -m g:${STEP_CA_USER}:r  "${STEP_CA_CONFIG_DIR}/certs" "${STEP_CA_CONFIG_DIR}/secrets" 2>/dev/null || true
fi

# ---------------------------------------------------------------------------
# Python venv + dependencies
# ---------------------------------------------------------------------------
echo "==> Creating Python virtual environment..."
if [[ ! -d "${VENV}" ]]; then
    python3 -m venv "${VENV}"
fi
chown -R "${APP_USER}:${APP_USER}" "${VENV}"

echo "==> Installing Python dependencies..."
sudo -u "${APP_USER}" "${PIP}" install --upgrade pip
sudo -u "${APP_USER}" "${PIP}" install -r "${APP_HOME}/requirements.txt"

echo "==> Installing frontend dependencies + building Tailwind CSS..."
if ! command -v npm &>/dev/null; then
    echo "    ERROR: npm not found on PATH — Tailwind CSS can't be built, UI would render unstyled." >&2
    exit 1
fi
if ! sudo -u "${APP_USER}" bash -c "cd ${APP_HOME} && npm install"; then
    echo "    ERROR: npm install failed. Fix the errors above and re-run install.sh." >&2
    exit 1
fi
if ! sudo -u "${APP_USER}" bash -c "cd ${APP_HOME} && npm run build:css"; then
    echo "    ERROR: npm run build:css failed. The UI would render unstyled." >&2
    exit 1
fi
if [[ ! -s "${APP_HOME}/static/css/app.css" ]]; then
    echo "    ERROR: ${APP_HOME}/static/css/app.css is missing or empty after build." >&2
    exit 1
fi
echo "    Tailwind CSS built: $(wc -c < "${APP_HOME}/static/css/app.css") bytes"

# ---------------------------------------------------------------------------
# Directories + self-signed TLS cert
# ---------------------------------------------------------------------------
echo "==> Creating runtime directories..."
mkdir -p "${CERTS_DIR}" "/run/forgedca"
chown "${APP_USER}:${APP_USER}" "${CERTS_DIR}" "/run/forgedca"

echo "==> Generating self-signed TLS cert for web UI..."
if [[ ! -f "${CERTS_DIR}/forgedca.crt" ]]; then
    openssl req -x509 -nodes -days 3650 \
        -newkey rsa:4096 \
        -keyout "${CERTS_DIR}/forgedca.key" \
        -out "${CERTS_DIR}/forgedca.crt" \
        -subj "/CN=forgedca/O=ForgedCA/C=US" 2>/dev/null
    chmod 600 "${CERTS_DIR}/forgedca.key"
    chown -R "${APP_USER}:${APP_USER}" "${CERTS_DIR}"
fi

# ---------------------------------------------------------------------------
# Generate secrets
# ---------------------------------------------------------------------------
echo "==> Generating application secrets..."
SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(50))')"
FIELD_ENCRYPTION_KEY="$(python3 -c 'import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())')"
FORGEDCA_DB_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
STEP_CA_DB_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"

# ---------------------------------------------------------------------------
# Postgres: roles + databases
# ---------------------------------------------------------------------------
echo "==> Provisioning Postgres roles and databases..."
if [[ ! -f "${APP_HOME}/.db-provisioned" ]]; then
    # Pipe SQL via stdin — keeps passwords out of a temp file on disk.
    if sed \
            -e "s|{{ FORGEDCA_DB_PASSWORD }}|${FORGEDCA_DB_PASSWORD}|g" \
            -e "s|{{ STEP_CA_DB_PASSWORD }}|${STEP_CA_DB_PASSWORD}|g" \
            "${APP_HOME}/deploy/postgres-init.sql.template" \
        | sudo -u postgres psql -v ON_ERROR_STOP=1 -q; then
        touch "${APP_HOME}/.db-provisioned"
        chown "${APP_USER}:${APP_USER}" "${APP_HOME}/.db-provisioned"
        echo "    Databases 'forgedca' and 'step_ca' created."
    else
        echo "ERROR: Postgres provisioning failed." >&2
        exit 1
    fi
else
    echo "    Databases already provisioned — skipping (remove ${APP_HOME}/.db-provisioned to re-run)"
fi

# ---------------------------------------------------------------------------
# .env
# ---------------------------------------------------------------------------
echo "==> Writing ${APP_HOME}/.env..."
ENV_FILE="${APP_HOME}/.env"
if [[ ! -f "${ENV_FILE}" ]]; then
    cat > "${ENV_FILE}" <<EOF
SECRET_KEY=${SECRET_KEY}
DEBUG=False
ALLOWED_HOSTS=*
WEB_PORT=${PORT}
FIELD_ENCRYPTION_KEY=${FIELD_ENCRYPTION_KEY}

# ForgedCA application DB
DB_NAME=forgedca
DB_USER=forgedca
DB_PASSWORD=${FORGEDCA_DB_PASSWORD}
DB_HOST=127.0.0.1
DB_PORT=5432

# step-ca's own DB (shared cluster, separate logical DB)
STEP_CA_DB_NAME=step_ca
STEP_CA_DB_USER=step_ca
STEP_CA_DB_PASSWORD=${STEP_CA_DB_PASSWORD}
STEP_CA_DB_HOST=127.0.0.1
STEP_CA_DB_PORT=5432

# Celery / Redis
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0

DJANGO_LOG_FILE=${LOG_DIR}/django.log
EOF
    chmod 600 "${ENV_FILE}"
    chown "${APP_USER}:${APP_USER}" "${ENV_FILE}"
    echo "    .env written."
else
    echo "    .env already exists — skipping."
fi

# ---------------------------------------------------------------------------
# Nginx
# ---------------------------------------------------------------------------
echo "==> Configuring Nginx..."
if [[ "${PKG_MANAGER}" == "apt" ]]; then
    NGINX_CONF_FILE="${NGINX_CONF_DIR}/forgedca"
    sed -e "s|{{ WEB_PORT }}|${PORT}|g" \
        "${APP_HOME}/deploy/nginx.conf.template" > "${NGINX_CONF_FILE}"
    [[ ! -L "${NGINX_ENABLED_DIR}/forgedca" ]] && ln -s "${NGINX_CONF_FILE}" "${NGINX_ENABLED_DIR}/forgedca"
    [[ -L "${NGINX_ENABLED_DIR}/default" ]] && rm -f "${NGINX_ENABLED_DIR}/default"
else
    NGINX_CONF_FILE="${NGINX_CONF_DIR}/forgedca.conf"
    sed -e "s|{{ WEB_PORT }}|${PORT}|g" \
        "${APP_HOME}/deploy/nginx.conf.template" > "${NGINX_CONF_FILE}"
fi
nginx -t 2>/dev/null && echo "    Nginx config valid."

cat > /etc/sudoers.d/forgedca-nginx <<EOF
${APP_USER} ALL=(ALL) NOPASSWD: /usr/sbin/nginx -s reload
${APP_USER} ALL=(ALL) NOPASSWD: /usr/sbin/nginx -t
${APP_USER} ALL=(ALL) NOPASSWD: /usr/bin/tee ${NGINX_CONF_FILE}
${APP_USER} ALL=(ALL) NOPASSWD: /usr/bin/tee ${APP_HOME}/deploy/acme-challenge.conf
EOF
chmod 440 /etc/sudoers.d/forgedca-nginx

# Let the forgedca web UI start/stop/reload step-ca after the install wizard
# renders ca.json. Narrower than blanket systemctl access.
cat > /etc/sudoers.d/forgedca-stepca <<EOF
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
chmod 440 /etc/sudoers.d/forgedca-stepca

# SELinux
if [[ "${PKG_MANAGER}" =~ ^(dnf|yum)$ ]] && command -v getenforce &>/dev/null; then
    SELINUX_STATUS="$(getenforce 2>/dev/null || echo Disabled)"
    if [[ "${SELINUX_STATUS}" == "Enforcing" || "${SELINUX_STATUS}" == "Permissive" ]]; then
        setsebool -P httpd_can_network_connect 1 2>/dev/null || true
        if command -v semanage &>/dev/null; then
            semanage port -l 2>/dev/null | grep -qw "${PORT}" || \
                semanage port -a -t http_port_t -p tcp "${PORT}" 2>/dev/null || true
        fi
        command -v restorecon &>/dev/null && restorecon -R "${APP_HOME}" 2>/dev/null || true
    fi
fi

# ---------------------------------------------------------------------------
# Systemd units
# ---------------------------------------------------------------------------
echo "==> Installing systemd units..."
cp "${APP_HOME}/deploy/gunicorn.service.template" /etc/systemd/system/forgedca-gunicorn.service
cp "${APP_HOME}/deploy/celery.service.template"   /etc/systemd/system/forgedca-celery.service
cp "${APP_HOME}/deploy/step-ca.service.template"  /etc/systemd/system/step-ca.service
systemctl daemon-reload

# ---------------------------------------------------------------------------
# Migrations + static
# ---------------------------------------------------------------------------
# All manage.py invocations below run with cwd=${APP_HOME}. Python's
# sys.path[0] gets set to cwd on `manage.py shell -c` / makemigrations, which
# means `apps.core` etc. would otherwise resolve from wherever the admin
# happened to be when they invoked install.sh — including a source checkout
# the forgedca user can't write to.
echo "==> Regenerating any model migrations the repo is missing..."
sudo -u "${APP_USER}" bash -c "cd ${APP_HOME} && \
    DJANGO_SETTINGS_MODULE=forgedca.settings.production \
    ${PYTHON} manage.py makemigrations --noinput" 2>&1 | tail -10 || true

echo "==> Running database migrations..."
sudo -u "${APP_USER}" bash -c "cd ${APP_HOME} && \
    DJANGO_SETTINGS_MODULE=forgedca.settings.production \
    ${PYTHON} manage.py migrate --noinput" 2>&1 | tail -5 || true

echo "==> Collecting static files..."
sudo -u "${APP_USER}" bash -c "cd ${APP_HOME} && \
    DJANGO_SETTINGS_MODULE=forgedca.settings.production \
    ${PYTHON} manage.py collectstatic --noinput" 2>&1 | tail -3 || true

# ---------------------------------------------------------------------------
# Admin account — will prompt the user to set password on first login
# ---------------------------------------------------------------------------
echo "==> Creating admin user..."
DEFAULT_ADMIN_PASS="Password!"
FORCE_CHANGE=true

if [[ -n "${FORGEDCA_ADMIN_USER:-}" && -n "${FORGEDCA_ADMIN_PASS:-}" ]]; then
    ADMIN_USER="${FORGEDCA_ADMIN_USER}"
    ADMIN_PASS="${FORGEDCA_ADMIN_PASS}"
    [[ "${ADMIN_PASS}" != "${DEFAULT_ADMIN_PASS}" ]] && FORCE_CHANGE=false
else
    read -rp "    Admin username [admin]: " ADMIN_USER
    ADMIN_USER="${ADMIN_USER:-admin}"
    echo "    (Press Enter to use the default password '${DEFAULT_ADMIN_PASS}' — you will be forced to change it at first login.)"
    read -rsp "    Admin password: " ADMIN_PASS
    echo ""
    if [[ -z "${ADMIN_PASS}" ]]; then
        ADMIN_PASS="${DEFAULT_ADMIN_PASS}"
    else
        FORCE_CHANGE=false
        read -rsp "    Confirm password: " ADMIN_PASS2
        echo ""
        [[ "${ADMIN_PASS}" != "${ADMIN_PASS2}" ]] && { echo "Passwords did not match."; exit 1; }
    fi
fi

# Idempotent superuser create/update via manage.py shell. More reliable
# than createsuperuser --noinput (which trips on empty REQUIRED_FIELDS)
# and re-runnable — if the admin exists, the password is reset. Also sets
# must_change_password=True whenever the default password is in use, so
# the first login march is: change password → enrol MFA → install wizard.
cd "${APP_HOME}"
sudo -u "${APP_USER}" \
    FORGEDCA_BOOTSTRAP_ADMIN_USER="${ADMIN_USER}" \
    FORGEDCA_BOOTSTRAP_ADMIN_PASS="${ADMIN_PASS}" \
    FORGEDCA_BOOTSTRAP_FORCE_CHANGE="${FORCE_CHANGE}" \
    DJANGO_SETTINGS_MODULE=forgedca.settings.production \
    "${PYTHON}" "${APP_HOME}/manage.py" shell -c "
import os
from django.contrib.auth import get_user_model
from apps.core.models import UserProfile, MFAConfig
User = get_user_model()
username = os.environ['FORGEDCA_BOOTSTRAP_ADMIN_USER']
password = os.environ['FORGEDCA_BOOTSTRAP_ADMIN_PASS']
force_change = os.environ['FORGEDCA_BOOTSTRAP_FORCE_CHANGE'] == 'true'
u, created = User.objects.get_or_create(
    username=username,
    defaults={'email': username + '@localhost', 'is_staff': True, 'is_superuser': True},
)
u.set_password(password)
u.is_staff = True
u.is_superuser = True
u.is_active = True
u.save()
profile, _ = UserProfile.objects.get_or_create(user=u)
profile.must_change_password = force_change
profile.save(update_fields=['must_change_password'])
MFAConfig.load()  # ensures default (enforce_mfa=True) exists
print('    Superuser {} ({}), must_change_password={}.'.format(
    username, 'created' if created else 'password reset', force_change))
"

# ---------------------------------------------------------------------------
# Enable + start services
# ---------------------------------------------------------------------------
echo "==> Enabling and starting services..."
for SVC in "${POSTGRES_SVC}" "${REDIS_SVC}" nginx forgedca-gunicorn forgedca-celery; do
    systemctl enable "${SVC}" 2>/dev/null || true
    systemctl restart "${SVC}" 2>/dev/null || systemctl start "${SVC}" 2>/dev/null || true
    echo "    ${SVC}: $(systemctl is-active "${SVC}" 2>/dev/null || echo 'unknown')"
done

# step-ca isn't started here — the install wizard starts it after the admin
# picks a role and the ca.json is rendered.

PRIMARY_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"

echo ""
echo "============================================================"
echo "  ForgedCA installation complete!"
echo "============================================================"
echo ""
echo "  Access URL : https://${PRIMARY_IP}:${PORT}"
echo "  Admin user : ${ADMIN_USER}"
echo ""
echo "  NOTE: Your browser will show a self-signed certificate"
echo "  warning. This is expected. Click 'Advanced' and proceed."
echo ""
echo "  Next steps (in the browser):"
echo "    1. Change the default admin password"
echo "    2. Enroll TOTP MFA"
echo "    3. Run the install wizard: pick Root / Intermediate / Issuing"
echo ""
echo "  Logs:   ${LOG_DIR}/"
echo "  Config: ${APP_HOME}/.env"
echo "============================================================"
