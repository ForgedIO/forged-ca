# ForgedCA

**Version 0.1.0-alpha** — scaffold only, not yet runnable end-to-end

> **To update an existing install:** `git pull origin main && sudo ./update.sh`

An opinionated, open-source ACME PKI platform built on [step-ca](https://smallstep.com/docs/step-ca/).

ForgedCA aims to be the easiest way to stand up a production-grade private PKI on-prem. The bar we're building against: *a non-PKI-expert admin can stand up a working multi-tier CA and distribute trust to their fleet in under an hour.*

Made by **[ForgedIO](https://github.com/ForgedIO)**.

---

## Status

**Day 1 of development.** The repo currently contains the full project scaffold, installer, and deploy templates. The Django apps are stubbed — no working web UI yet. See [`docs/roadmap.md`](docs/roadmap.md) for v1 scope and milestones.

## Vision

- **Web-based install wizard** — pick whether a server is a Root CA, Intermediate CA, Issuing CA, or any combination
- **ACME issuance** with HTTP-01 and (where feasible) DNS-01 validation
- **Federation** — any server deployed as Intermediate or Issuing can point back at the Root to auto-enroll
- **Fleet-wide management** — logging into any node shows a live dashboard of the entire PKI (live-queried from peers)
- **Trust-store deployment helpers** — one-click GPO ADMX, Intune profiles, and ready-to-paste snippets for cert-manager, Traefik, Caddy, nginx, certbot, acme.sh
- **Flexible lifetimes** — long-lived CA certs, short-lived ACME leaves, non-ACME templates bounded by the issuer's remaining lifetime
- **Offline Root CA support** — USB sneakernet ceremony for orgs that require an air-gapped Root
- **Revocation + OCSP** that an admin can operate without reading a whitepaper
- **MFA mandatory** on first admin login — TOTP for local / LDAP / generic OIDC / SAML users; skipped for Entra ID and Duo-layered logins where the IdP provides MFA
- **IdPs in v1:** Local, LDAP, Entra ID, Generic SAML 2.0, Generic OIDC, and Duo as a layered MFA provider
- **Email via SMTP or Microsoft Graph API**; syslog forwarding required

## Requirements

- A dedicated Linux server (not the Proxmox host if using Proxmox; not a shared appliance)
- **Python 3.10+** (installed automatically by `install.sh`)
- **PostgreSQL 13+** (installed automatically by `install.sh`)
- Root/sudo access for the installer
- Network reachability between nodes if deploying multi-tier federation (except for offline Root, which uses USB sneakernet)

### Supported operating systems

| Family | Tested distros |
|---|---|
| **Debian / Ubuntu** | Ubuntu 22.04 LTS, Ubuntu 24.04 LTS, Debian 11, Debian 12 |
| **RHEL / CentOS Stream / Rocky** | CentOS Stream 9, CentOS Stream 10, Rocky Linux 8/9, AlmaLinux 8/9, RHEL 8/9 |
| **SUSE / openSUSE** | openSUSE Leap 15, openSUSE Tumbleweed |

The installer auto-detects `apt`, `dnf`, `yum`, or `zypper` and installs the correct packages for your distribution.

**SELinux note (RHEL/CentOS/Rocky):** The installer applies the required policy automatically — `httpd_can_network_connect`, HTTPS port labelling, and `restorecon` on the app directory.

### Why root/sudo is required

- Creates `forgedca` and `step-ca` system users and groups
- Writes application files to `/opt/forgedca/` and step-ca state to `/etc/step-ca/` + `/var/lib/step-ca/`
- Installs system packages (Postgres, nginx, step-ca, Python deps)
- Writes systemd unit files to `/etc/systemd/system/`
- Configures nginx, including a sudoers rule so the `forgedca` service user can reload nginx without a password
- Generates a self-signed TLS certificate for the web UI

`uninstall.sh` also requires root.

## Quick install

```bash
git clone https://github.com/ForgedIO/forged-ca.git
cd forged-ca
sudo ./install.sh
```

Custom HTTPS port:

```bash
sudo ./install.sh --port 9443
```

The installer:
1. Creates the `forgedca` and `step-ca` system users
2. Installs Python, Postgres, Redis, nginx, Node/npm, and step-ca
3. Creates a Python virtualenv and installs dependencies
4. Bootstraps two Postgres databases: `forgedca` (app state) and `step_ca` (step-ca's own state)
5. Generates a self-signed TLS certificate for the web UI
6. Configures nginx as a reverse proxy
7. Installs systemd units for Gunicorn and Celery (step-ca's unit is installed but not started — the wizard brings it up after the admin picks a role)
8. Runs database migrations and creates an admin account

After install, open `https://<your-server-ip>:8443` and log in with the admin account created during installation.

## First login

The installer prompts for an admin account. If you pressed Enter to skip the password prompt, the default is:

| Field | Value |
|---|---|
| Username | `admin` (or whatever you entered) |
| Password | `Password!` |

You will be **forced to change the password on first login** and **enroll TOTP MFA** before you can access anything else. After MFA is set up, the install wizard launches — pick a role (Root / Intermediate / Issuing, any combination), bootstrap the CA, and you're running.

## Updating

```bash
cd /path/to/forged-ca   # wherever you cloned the repo
sudo ./update.sh
```

`update.sh` runs `git pull`, syncs files into `/opt/forgedca/`, updates dependencies, runs migrations, rebuilds Tailwind CSS, and restarts services. TLS certs, CA keys, `.env`, and the Postgres DB are preserved.

## Uninstalling

```bash
sudo ./uninstall.sh
```

Removes all services, files, the system users, and **both databases**. ⚠️ **If you use offline Root mode, back up `/etc/step-ca/` first — the CA keys cannot be recovered.**

Preserve data:

```bash
sudo ./uninstall.sh --keep-data
```

## Architecture

- **PKI engine:** step-ca (we wrap and orchestrate — we do not reimplement)
- **Web framework:** Django 4.2 + HTMX
- **UI framework:** Tailwind CSS + DaisyUI
- **Task queue:** Celery + Redis
- **Database:** PostgreSQL (two logical DBs — `forgedca` and `step_ca`)
- **Reverse proxy:** nginx (TLS termination for the web UI)
- **Federation:** HTTPS + mTLS between nodes; dashboard aggregates peer status live on demand

See the full architecture plan in `docs/roadmap.md` and `CLAUDE.md`.

## License

TBD. Will be one of MIT / Apache 2.0.

## Community

Issues, PRs, and feature requests welcome at https://github.com/ForgedIO/forged-ca.
