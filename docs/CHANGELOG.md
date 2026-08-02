# ForgedCA Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0-alpha] — 2026-08-02

Slices 1 through 3.7. The scaffold from 0.1.0 becomes a working single-node PKI: install, log in, enroll MFA, run the wizard, and the box issues certs over ACME against a Root → Intermediate → Issuing chain it generated itself. Federation is still ahead.

This entry backfills roughly four months of shipped work that never made it into the changelog — cut as one release rather than reconstructing intermediate version boundaries after the fact.

### Added
- **Slice 1 — CA bootstrap.** Login, role-select wizard (Root / Intermediate / Issuing, any combination), local generation of the full chain, and trust-chain download endpoints. Wizard warns when Root + Issuing is picked without an Intermediate; lifetime fields carry recommendation help text and a live years/days readout
- **Slice 1.5 — account security.** Forced password change on first login, then TOTP MFA enrollment with recovery codes, then the wizard
- **Slice 1.7 — the UI trusts itself.** The wizard issues the admin UI's own leaf cert and swaps nginx onto it, so installing the Root on an admin's device turns the lock green on this very UI. Signing is deferred to a post-wizard admin action on Root-/Intermediate-only nodes. Inline PEM viewer with copy and re-download on every trust pane
- **Slice 1.8 — information architecture.** Left sidebar with a dedicated page per menu item, replacing single-page navigation; role-gated so nodes only show what they can do
- **Slice 2A — daemon lifecycle.** step-ca start / stop / live status from Settings, with an in-UI `journalctl` log tail and a Stop button that stays reachable during a crash loop
- **Slice 2B — ACME provisioners.** Provisioner model, admin page, and `ca.json` wiring; `ca.json` re-renders on every deploy so step-ca picks up config changes
- **Slice 2C — ACME client onboarding.** Tabbed per-client snippets for `step`, `certbot`, `acme.sh`, cert-manager, Traefik, Caddy, and nginx
- **Slice 3 — certificate templates.** CRUD UI, template-per-provisioner binding, lifetime bounds, and a seeded system "Web Server" template so every provisioner always has a binding. Signer policy is ForgedCA-only — no external-CA delegation
- **Slice 3.7 — EKU / Key Usage policy.** Friendly Extended Key Usage and Key Usage checkboxes on each template, a custom-OID escape hatch, exclusivity guardrails for OCSP signing and Time stamping, and 14 one-click use-case presets (web server, RADIUS / EAP-TLS, guest portal, pxGrid mTLS, smart card logon, S/MIME, code signing, IKEv2 VPN, IPsec, OCSP responder, TSA) that autofill the right EKU + KU pairing
- **Slice 3.7 enforcement.** Each ACME provisioner emits `options.x509.template` rendered from its bound template, so step-ca writes exactly the declared EKU and KU bits on every issued cert regardless of what the CSR requests. Subject and SANs still flow through from the CSR
- Light / dark theme toggle; ForgedCA brand palette wired into Tailwind and DaisyUI; Keyhole Seal logo, wordmark, and favicons
- CA signing keys encrypted at rest with an auto-generated passphrase
- Web UI SANs always carry `config.hostname` and are editable from Settings
- `install.sh` / `update.sh` fail loudly if the Tailwind CSS build breaks, rather than shipping an unstyled UI
- `docs/keyfactor-research.md` — capability analysis behind the deferred endpoint-lifecycle scope

### Changed
- Architecture refactor across `core`, `wizard`, and `trust`: one view per file, class-based views, `helpers/` per app, imports at top
- Trust bundle now includes the Issuing CA and recommends it over a Root-only install
- Web UI cert switched to RSA 2048 to match the shape ACME issues
- `default_webui_sans` no longer seeds non-FQDN values (`localhost`, OS short hostname)
- `update.sh` re-execs itself when `git pull` advances HEAD, and re-renders nginx on update
- `Strict-Transport-Security: max-age=0` so a stale HSTS pin can't lock admins out after a cert swap
- Roadmap restructured as a single-server-first slice sequence; trust-store helpers promoted into v1; Settings and post-quantum slices added

### Fixed
- step-ca `activating` loop — dropped `--password-file`; namespace failure — dropped `/var/log/step-ca` and added a start limit; CA directory permissions healed so step-ca can read the chain
- Root and Intermediate `pathLen` widened so Firefox accepts the 3-tier chain
- Issuing + Intermediate now bundled into step-ca's `crt` field for a complete 3-tier chain
- `/change-password/` ↔ `/wizard/` redirect loop
- Admin bootstrap made idempotent; `manage.py` runs from `/opt/forgedca` so `sys.path[0]` is the deployed code
- Several leaking Django template comments and a `TemplateSyntaxError` from a duplicated `block content`
- Oversized trust-pane icons fixed at the CSS layer rather than per-template; brand SVGs given real intrinsic dimensions

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
