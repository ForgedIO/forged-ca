# ForgedCA Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0-alpha] — 2026-04-18

Initial scaffold. No working web UI yet — this release stands up the repo shape, installer skeleton, and deploy templates against which v1 will be built.

### Added
- Top-level repo layout: `apps/`, `forgedca/`, `deploy/`, `templates/`, `help/`, `docs/`, `static/`, `scripts/`, `tests/`
- Django 4.2 project scaffold (`forgedca/`) with `base.py` / `production.py` / `dev.py` settings, Celery, WSGI, ASGI entrypoints
- App stubs (AppConfig only) for: `core`, `wizard`, `authconfig`, `emailconfig`, `nodes`, `ca`, `federation`, `issuance`, `acme`, `templates_app`, `trust`, `dashboard`, `ceremony`, `truststore`, `auditlog`
- PostgreSQL database layout — two logical DBs (`forgedca`, `step_ca`) on one cluster, bootstrapped by `deploy/postgres-init.sql.template`
- Syslog handler wiring in `settings/base.py` (destination configured at runtime by `SyslogConfig` model, to be built)
- `install.sh` with multi-distro detection (apt / dnf / yum / zypper), step-ca binary fallback install, admin account creation, self-signed TLS cert generation
- `update.sh` with self-`git pull` and dependency/migration/static refresh
- `uninstall.sh` with `--keep-data` option; drops both Postgres DBs in full-removal mode
- Deploy templates: `nginx.conf.template`, `gunicorn.service.template`, `celery.service.template`, `step-ca.service.template`, `postgres-init.sql.template`
- `requirements.txt`: Django, Celery, psycopg[binary], pyotp, django-auth-ldap, django-allauth, python3-saml, msal, duo-universal, django-encrypted-model-fields, cryptography, Markdown
- `package.json` + `tailwind.config.js` + `postcss.config.js` with Tailwind CSS + DaisyUI build chain
- README with project status, supported OS, install/update/uninstall instructions, and links to `docs/roadmap.md`
- `docs/roadmap.md` tracking v1 scope and v2-deferred items
