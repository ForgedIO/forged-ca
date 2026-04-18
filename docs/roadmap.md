# ForgedCA Roadmap

This document tracks what's in v1 scope, what's explicitly deferred to v2, and rough progress against v1.

## v1 scope (the plan we're building to)

### Core PKI
- [ ] step-ca installation, config rendering, and lifecycle management (`apps/ca/`)
- [ ] Any-combination role model: Root / Intermediate / Issuing per node
- [ ] Online multi-tier federation (Root → Intermediate → Issuing)
- [ ] Offline Root support via USB sneakernet ceremony (Root-only nodes)
- [ ] ACME provisioners with HTTP-01 validation
- [ ] ACME DNS-01 validation (as a plugin, at least Cloudflare + Route53)
- [ ] Non-ACME CSR signing UI with templates and opt-in passthrough
- [ ] Revocation (passive by default; active CRL/OCSP per-provisioner toggle)

### Templates
- [ ] `CertTemplate` model with EKU / KU / validity / name-constraint fields
- [ ] Create-from-Issuing-pushes-up-to-Intermediate flow
- [ ] Issuing-CA hourly refresh of templates from parent Intermediate
- [ ] Intermediate-to-Intermediate peering for cross-scope template sharing
- [ ] ACME-provisioner binds to a template; default "Web Server (Server + optional Client Auth)"
- [ ] EKU intersection logic (CSR ∩ template, `serverAuth` forced-always on Web Server)

### Federation
- [ ] mTLS federation CA bootstrap on online Root
- [ ] Bootstrap token mint + exchange flow for adding peers
- [ ] `/fed/v1/` REST endpoints (bootstrap, peers, status, csr, trust-chain, templates, health)
- [ ] Live-aggregation dashboard (parallel peer `/status` queries, 30s Redis cache)
- [ ] Per-node trust-chain download — public by default, admin-toggle to require auth

### UX
- [ ] First-run install wizard (admin + MFA → role → federation → lifetimes → key/CSR → ACME defaults)
- [ ] Role-gated navigation (offline Root sees ceremony UI only; etc.)
- [ ] ACME Client Onboarding page per provisioner (directory URL, fingerprint, copy-paste commands for `step`, `certbot`, `acme.sh`, cert-manager, Traefik, Caddy, nginx)
- [ ] Trust-store distribution helpers (GPO ADMX generator, Intune configuration profile generator)
- [ ] Help system (markdown per page, loaded via HTMX into a side panel)
- [ ] Dark mode

### Identity + Security
- [ ] Local accounts with forced password change on first login
- [ ] TOTP MFA mandatory for local/LDAP/SAML/OIDC users
- [ ] Recovery codes + email-bypass for TOTP
- [ ] LDAP backend (lifted from proxmigrate)
- [ ] Entra ID backend (lifted, dedicated config with its nice UX)
- [ ] Generic SAML 2.0 backend
- [ ] Generic OIDC backend
- [ ] Duo Universal Prompt as a layered MFA provider on top of any primary IdP
- [ ] SMTP email backend
- [ ] Microsoft Graph API email backend
- [ ] Syslog forwarding (DB-driven destination config)
- [ ] Audit log (append-only, per-node)

### Distribution
- [ ] `install.sh` multi-distro (apt / dnf / yum / zypper) with step-ca + Postgres bootstrap
- [ ] `update.sh` self-pulls and applies the upgrade in one command
- [ ] `uninstall.sh` with `--keep-data` option
- [ ] LXC one-liner helper (proxmox-friendly)
- [ ] `install.sh --port <n>` flag
- [ ] Air-gap support (pre-seeded `vendor/` dir for pip installs)

## v2 and beyond (explicitly deferred)

- Fleet-sync of IdP / email / syslog configs (v1: per-node, configured independently)
- Event-log federation + gossip (v1: live queries only, no mirrored state)
- Shared-Postgres Issuing-CA HA pool behind a load balancer (v1: admins stand up independent Issuing nodes under the same Intermediate)
- CRL / OCSP aggregation across nodes
- Transitive Intermediate peering / full Intermediate mesh (v1: pairwise-only)
- Kubernetes-native deployment (Helm chart / operator)
- Trust-store distribution beyond GPO + Intune (JAMF, Ansible roles, Puppet modules)
- SSH host-cert provisioning via step-ca's SSH CA feature
- HSM / PKCS#11 integration for CA key material
- Cert lifecycle metrics dashboard (SLOs on issuance latency, renewal failure rate)
- Public HTTPS hosting support for ACME validation (currently assumes private network)

## Progress log

### 0.1.0-alpha — 2026-04-18
- Initial repo scaffold: directory layout, Django project, app stubs
- `install.sh` / `update.sh` / `uninstall.sh` skeletons with multi-distro detection
- Deploy templates: nginx, gunicorn, celery, step-ca systemd unit, Postgres bootstrap SQL
- `requirements.txt` + `package.json` with Tailwind + DaisyUI wiring
- `CLAUDE.md`, plan document, architecture README
