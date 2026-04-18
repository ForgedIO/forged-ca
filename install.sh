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
# step-ca installation
# ---------------------------------------------------------------------------
echo "==> Installing step-ca and step CLI..."
if ! command -v step-ca &>/dev/null; then
    STEP_CA_VERSION="0.28.1"
    ARCH="$(uname -m)"
    case "${ARCH}" in
        x86_64)  STEP_ARCH="amd64" ;;
        aarch64) STEP_ARCH="arm64" ;;
        *) echo "    WARN: unsupported architecture '${ARCH}' for step-ca auto-install" >&2 ;;
    esac
    if [[ -n "${STEP_ARCH:-}" ]]; then
        TMPDIR="$(mktemp -d)"
        cd "${TMPDIR}"
        for pkg in step-ca step-cli; do
            URL="https://github.com/smallstep/certificates/releases/download/v${STEP_CA_VERSION}/${pkg}_linux_${STEP_CA_VERSION}_${STEP_ARCH}.tar.gz"
            [[ "${pkg}" == "step-cli" ]] && URL="https://github.com/smallstep/cli/releases/download/v${STEP_CA_VERSION}/step_linux_${STEP_CA_VERSION}_${STEP_ARCH}.tar.gz"
            if wget -q "${URL}" -O "${pkg}.tar.gz"; then
                tar -xzf "${pkg}.tar.gz"
                find . -type f -name "step-ca" -exec cp {} /usr/bin/step-ca \;
                find . -type f -name "step" -exec cp {} /usr/bin/step \;
            else
                echo "    WARN: could not download ${pkg} from ${URL} — install step-ca manually"
            fi
        done
        chmod 755 /usr/bin/step-ca /usr/bin/step 2>/dev/null || true
        cd "${SCRIPT_DIR}"
        rm -rf "${TMPDIR}"
    fi
else
    echo "    step-ca already installed: $(step-ca version 2>/dev/null | head -1)"
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
chown -R "${STEP_CA_USER}:${STEP_CA_USER}" "${STEP_CA_CONFIG_DIR}" "${STEP_CA_DATA_DIR}"
chmod 0750 "${STEP_CA_CONFIG_DIR}"
chmod 0700 "${STEP_CA_DATA_DIR}"

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

echo "==> Installing frontend dependencies..."
if command -v npm &>/dev/null; then
    sudo -u "${APP_USER}" bash -c "cd ${APP_HOME} && npm install 2>&1 | tail -1" || true
    sudo -u "${APP_USER}" bash -c "cd ${APP_HOME} && npm run build:css 2>&1 | tail -1" || true
else
    echo "    WARN: npm not found — Tailwind CSS will not be built"
fi

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
echo "==> Running database migrations..."
sudo -u "${APP_USER}" \
    DJANGO_SETTINGS_MODULE=forgedca.settings.production \
    "${PYTHON}" "${APP_HOME}/manage.py" migrate --noinput 2>&1 | tail -5 || true

echo "==> Collecting static files..."
sudo -u "${APP_USER}" \
    DJANGO_SETTINGS_MODULE=forgedca.settings.production \
    "${PYTHON}" "${APP_HOME}/manage.py" collectstatic --noinput 2>&1 | tail -3 || true

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

sudo -u "${APP_USER}" \
    DJANGO_SUPERUSER_USERNAME="${ADMIN_USER}" \
    DJANGO_SUPERUSER_PASSWORD="${ADMIN_PASS}" \
    DJANGO_SUPERUSER_EMAIL="" \
    DJANGO_SETTINGS_MODULE=forgedca.settings.production \
    "${PYTHON}" "${APP_HOME}/manage.py" createsuperuser --noinput 2>/dev/null || \
    echo "    (Superuser '${ADMIN_USER}' may already exist — skipping.)"

if [[ "${FORCE_CHANGE}" == "true" ]]; then
    sudo -u "${APP_USER}" \
        DJANGO_SETTINGS_MODULE=forgedca.settings.production \
        "${PYTHON}" "${APP_HOME}/manage.py" set_must_change_password "${ADMIN_USER}" 2>/dev/null || true
fi

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
