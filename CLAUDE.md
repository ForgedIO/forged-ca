# ForgedCA

Open-source ACME PKI platform built on [step-ca](https://smallstep.com/docs/step-ca/). Published by **ForgedIO** at https://github.com/ForgedIO/forged-ca.

## What we're building

A dramatically simpler alternative to Microsoft ADCS for on-prem private PKI. The bar is "a non-PKI-expert admin can stand up a working multi-tier CA and distribute trust to their fleet in under an hour."

### Core features

1. **Web-based installation wizard.** On first run, ask whether this server is a Root CA, Intermediate CA, Issuing CA, or all three.
2. **ACME issuance** with HTTP-01 and (where feasible) DNS-01 validation.
3. **Federation.** Any server deployed as Intermediate or Issuing CA can point back at the Root CA ("the first server deployed") to automatically receive and install its CA certificate from the chain above it.
4. **Fleet-wide management.** Logging into *any* node manages the entire PKI. Easy retrieval of the full trust-chain PEM or any individual cert in the chain. Must support multiple Intermediates and multiple Issuing CAs under them.
5. **Trust-store deployment helpers.** Wizards / generated instructions for distributing the root/intermediate certs via GPO, Intune, and other common mechanisms.
6. **Flexible lifetimes.**
   - Root, Intermediate, Issuing CA certs: long-term
   - ACME-issued leaf certs: short-term
   - Non-ACME templates (for servers that don't speak ACME): any lifetime *less than* the issuing CA's remaining lifetime
7. **Revocation + OCSP** that an admin can actually operate without reading a whitepaper.
8. **Dashboard** giving a single-pane view of the whole PKI across all federated nodes.

## Stack

- **Backend CA engine:** step-ca (do not reimplement — we're an opinionated installer + orchestrator + UI on top of it)
- **Reverse proxy / TLS terminator:** nginx
- **Web platform:** TBD (to be decided — evaluate based on ops simplicity, not developer fashion)
- **Database:** TBD (needs to handle PKI state, federation coordination, audit/revocation records)
- **Installer:** a single `install.sh` that provisions everything above end-to-end

## Design principles

- **Simplicity over feature breadth.** There are many free on-prem ACME PKI tools. Our edge is *ease of deployment and daily operation*, not a bigger feature matrix.
- **Not a commercial product.** We do not expect to sell this — licensing and packaging decisions should favor open-source distribution, not monetization hooks.
- **Safe defaults.** Private keys never leave the host that generated them. CA key material is never transmitted between federated nodes — only CSRs go up and signed certs come back.
- **Recoverable.** Every destructive operation (revocation, CA rotation, node removal) must be explained in the UI before it runs. No silent state changes.
- **Admin, not developer.** The primary user is a sysadmin standing this up for their org, not a developer. UX copy, error messages, and wizards should match that audience.

## Naming & conventions

- **Product / branding:** `ForgedCA` (PascalCase) — use in docs, UI copy, READMEs.
- **Repo, directory, package, binary:** `forged-ca` (kebab-case).
- **GitHub org:** `ForgedIO` (note the "d" — *Forged*, not *Forge*).

## Repo layout

Early stage — only `README.md`, `.gitignore`, and this file exist. Expected top-level layout once scaffolded (subject to change when stack is picked):

```
forged-ca/
├── install.sh          # one-shot installer
├── cmd/ or src/        # application code
├── web/                # dashboard + install wizard frontend
├── migrations/         # database schema
├── deploy/             # nginx templates, systemd units, etc.
├── docs/
└── scripts/
```

## What Claude should help with

- Architecture decisions (web framework, DB choice, federation protocol design)
- Writing the installer and systemd/nginx integration
- Building the install wizard and dashboard
- Designing the federation handshake between Root / Intermediate / Issuing nodes
- Trust-store distribution tooling (GPO ADMX templates, Intune configuration profiles, etc.)
- ACME flow integration with step-ca's native ACME provisioner

## What Claude should NOT do

- Reinvent step-ca internals — we wrap and orchestrate it.
- Add commercial / licensing / billing scaffolding unless explicitly asked.
- Invent features beyond what's in this doc without discussing first.
- Commit cert/key material — `.gitignore` already blocks `*.key`, `*.pem`, `*.crt`, `.step/`, etc. If you need fixtures, discuss the pattern before force-adding.

## Status

Day 1. No application code yet. Next likely work: pick the web stack and DB, then scaffold the installer and a minimal "Root CA mode" end-to-end before moving to federation.
