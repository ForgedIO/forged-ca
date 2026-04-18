# ForgedCA Roadmap

This document tracks **how** ForgedCA is being built, not just **what**. Work is split into thin slices that can be tested end-to-end on a single LXC/VM by a sysadmin pulling from `main`. Federation (multi-node) is the final layer — we prove every feature on a single "all roles" box first.

## Development principle: single-server first

Every feature in v1 lands in its single-node form (Root + Intermediate + Issuing on one box) **before** we start building the federation protocol. This keeps us from multiplying CA-level bugs across three boxes. Once every user-facing feature works on one node, the federation slices split the roles across multiple nodes.

## Slice sequence

Each slice is one testable deliverable. Check `docs/CHANGELOG.md` for per-commit detail.

### Foundations (single-server)
- [x] **Slice 1** — login + wizard + local Root/Intermediate/Issuing chain generation, trust-chain download endpoints
- [x] **Slice 1.5** — forced password change on first login, TOTP MFA enrollment with recovery codes, then wizard
- [x] **Architecture refactor** — one view per file, class-based views, helpers/ per app, imports at top
- [x] **Slice 1.7** — wizard issues the admin UI's own leaf cert and swaps nginx to it, so installing the Root on an admin's device immediately turns the lock green on this very UI; inline PEM viewer + copy/download on every trust pane
- [ ] **Slice 2** — step-ca daemon lifecycle (start/stop via systemctl), a default ACME provisioner, ACME Client Onboarding page (copy-paste commands for `step`, `certbot`, `acme.sh`, cert-manager, Traefik, Caddy, nginx), and a real leaf-cert enrollment demo against the local Issuing CA
- [ ] **Slice 3** — cert templates: CRUD UI, template-per-provisioner binding, default "Web Server (Server + optional Client Auth)" template
- [ ] **Slice 4** — non-ACME CSR signing UI: admin uploads CSR → picks a compatible template → signs; explicit "passthrough (advanced)" opt-in for bare-CSR signing
- [ ] **Slice 4.5** — Settings page: HTTPS port live-reconfig (8443 → 443 toggle with graceful reconnect), trust-download auth toggle, admin user management, node-level rename
- [ ] **Slice 5** — **Trust-store distribution helpers** (moved up from v2): Windows `.reg` / PowerShell / MSI, macOS `.mobileconfig`, Linux `/etc/ca-certificates` installer script, Firefox `policies.json`, GPO ADMX template, Intune configuration profile. One-click download per target so admins can deploy the Root to any fleet without reading distro docs
- [ ] **Slice 6** — local dashboard: rollup counts (issued, expiring soon, revoked) and a recent-issuances list with a revoke button
- [ ] **Slice 7** — revocation UI + per-node append-only audit log
- [ ] **Slice 8** — email backends: SMTP + Microsoft Graph API; password reset flow; MFA email-recovery bypass
- [ ] **Slice 9** — syslog forwarder settings (DB-driven destination, severity thresholds)
- [ ] **Slice 10** — IdPs: LDAP, Entra ID (dedicated UX), generic SAML 2.0, generic OIDC, Duo Universal Prompt as a layered MFA provider

### Federation (multi-server, starts at slice 11)
- [ ] **Slice 11** — federation mTLS CA bootstrap on online Root; bootstrap token mint + exchange flow; join-as-Intermediate wizard that submits a CSR to the Root and imports the signed cert
- [ ] **Slice 12** — join-as-Issuing under an existing Intermediate; live-aggregation dashboard (each node queries peers on demand for the fleet view)
- [ ] **Slice 13** — cert-template push-up (create on Issuing, canonical copy lives on Intermediate); pairwise Intermediate ↔ Intermediate peering for cross-scope template sharing
- [ ] **Slice 14** — offline Root ceremony (Root-only node, air-gapped): CSR-over-USB signing flow with fingerprint confirmation on import
- [ ] **Slice 15** — role-gated navigation polish, help system (markdown per page, HTMX side panel), dark mode sweep, README screenshots

### Crypto agility / post-quantum readiness
- [ ] **Slice 16** — key-type / signature-algorithm choice on the CA wizard. RSA-2048, RSA-4096, ECDSA P-256 (default, current step default), ECDSA P-384, Ed25519 shipped today. Hidden slot for ML-DSA-44/65/87 (FIPS 204) that flips visible the moment step-cli emits native PQC signatures. Architecture is PQC-ready now; the UI lights up upstream-first so we're not shipping certs browsers currently reject.

Slice numbers will shift as scope shakes out.

## v2 and beyond (explicitly deferred out of v1)

- Fleet-sync of IdP / email / syslog configs (v1: per-node, configured independently)
- Event-log federation + gossip (v1: live queries only, no mirrored state)
- Shared-Postgres Issuing-CA HA pool behind a load balancer (v1: admins stand up independent Issuing nodes under the same Intermediate)
- CRL / OCSP aggregation across nodes
- Transitive Intermediate peering / full Intermediate mesh (v1: pairwise-only)
- Kubernetes-native deployment (Helm chart / operator)
- Trust-store distribution beyond v1's Windows/macOS/Linux/Firefox/GPO/Intune kit (JAMF native, Puppet modules, Chef cookbooks)
- SSH host-cert provisioning via step-ca's SSH CA feature
- HSM / PKCS#11 integration for CA key material
- Cert lifecycle metrics dashboard (SLOs on issuance latency, renewal failure rate)
- Public HTTPS hosting support for ACME validation (currently assumes private network)

## Supported distros (installer matrix)

- Ubuntu 22.04 LTS, 24.04 LTS
- Debian 11, 12
- RHEL 8, 9; CentOS Stream 9, 10; Rocky 8, 9; AlmaLinux 8, 9
- openSUSE Leap 15, openSUSE Tumbleweed

Non-v1 packaging targets (Kubernetes / Helm, Docker, JAMF trust-store, etc.) are in the v2 list above.
