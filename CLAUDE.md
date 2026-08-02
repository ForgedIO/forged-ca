# ForgedCA

Open-source ACME PKI platform built on [step-ca](https://smallstep.com/docs/step-ca/). Published by **ForgedIO** at https://github.com/ForgedIO/forged-ca.

## Where things stand — read this first

Work is tracked as numbered **slices**. Two documents answer "what's done, what's left":

| Question | Document |
|---|---|
| **Which slices are complete / remaining?** | **[`docs/roadmap.md`](docs/roadmap.md)** — the status table at the top is the single source of truth |
| What changed, per release? | [`docs/CHANGELOG.md`](docs/CHANGELOG.md) |
| What is the next slice, in detail? | [`docs/slice-4-spec.md`](docs/slice-4-spec.md) |

**If you're asked to summarise slice status, read `docs/roadmap.md` — do not infer it from git log or from this file.**

As of 2026-08-02: slices 1 → 3.7 are shipped. A single node installs, runs the wizard, generates a Root → Intermediate → Issuing chain, and issues certs over ACME with EKU/KU policy enforced. **Slice 4** (non-ACME CSR signing) is next and is fully spec'd. Slice 3.5 (SCEP) was skipped over and is still open. Federation has not started.

Testbed: `cday@192.168.1.172` (hostname `RootCA`). Deploy with `cd ~/forged-ca && sudo ./update.sh`.

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
- **Web platform:** Django 4.2 + HTMX, served by Gunicorn (`forgedca-gunicorn.service`)
- **UI:** Tailwind CSS + DaisyUI (see the styling section below)
- **Database:** PostgreSQL — two logical DBs on one cluster, `forgedca` (app state) and `step_ca` (step-ca's own state)
- **Task queue:** Celery + Redis
- **Installer:** a single `install.sh` that provisions everything above end-to-end; `update.sh` redeploys, `uninstall.sh` removes

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

## Styling — Tailwind + DaisyUI, CSS-first for fixes

The UI layer uses **Tailwind CSS + DaisyUI**, compiled by `npm run build:css` into `static/css/app.css`. When the layout or an element is rendering wrong (sizing, spacing, colour, etc.), **fix it in the stylesheet (`static/css/app.src.css`), not by piling more utility classes onto every template**. Patching templates repeatedly is fragile and doesn't survive Tailwind scan hiccups or a forgotten rebuild.

Rules:

- **Global element fixes** — use `@layer base` for defaults that apply to every instance (e.g. default `svg` size so unsized icons don't fall back to the browser's 300×150).
- **Reusable component classes** — use `@layer components` (e.g. `.icon-sm`, `.icon-md` for named icon sizes, `.btn-download` for a repeated pattern). Compose with `@apply` if useful.
- **DaisyUI overrides** — target DaisyUI's generated classes inside `@layer components` when a DaisyUI default doesn't match the design; don't try to out-specificity-war it from templates.
- **Tailwind utilities still welcome for one-offs** — the goal isn't to abandon utility classes; it's to stop fighting them when a pattern repeats or a base element needs sane defaults.
- **Always rebuild CSS when a pattern changes** — `update.sh` runs `npm run build:css`, but during iterative dev a stale `static/css/app.css` can make "my class isn't working" look like a template bug when it's really a build bug. Prefer CSS-layer changes over template changes because they produce the same CSS whether the build scanned every template or not.

Apply this every time. Tailwind class churn in templates is a sign the fix belongs in CSS.

## Repo layout

```
forged-ca/
├── install.sh / update.sh / uninstall.sh
├── manage.py
├── forgedca/           # Django project — settings/{base,production,dev}.py, celery, wsgi
├── apps/               # one Django app per domain (see below)
├── templates/          # Django templates, one directory per app
├── static/             # css/app.src.css → css/app.css (built), img, js
├── deploy/             # nginx / systemd / postgres templates
├── docs/               # roadmap.md, CHANGELOG.md, slice specs
├── help/               # per-page help markdown (empty — Slice 15)
├── tests/              # test suite (empty — Slice 4 establishes it)
└── scripts/
```

**Apps:** `core`, `wizard`, `authconfig`, `emailconfig`, `nodes`, `ca`, `federation`,
`issuance`, `acme`, `templates_app`, `trust`, `dashboard`, `ceremony`, `truststore`,
`auditlog`. Several are still AppConfig-only stubs awaiting their slice.

**Per-app layout** (established convention — follow it):

```
apps/<app>/
├── models.py           # single file
├── forms.py            # single file
├── urls.py             # imports view classes from views/
├── views/
│   ├── __init__.py     # re-exports every view class
│   └── <one_page>.py   # exactly one class-based view per file
└── helpers/
    └── <topic>.py      # free functions; the real logic lives here
```

Views subclass `django.views.View` (or a generic) with `LoginRequiredMixin`, and keep
`get()`/`post()` thin. **Every import at the top of the file — never inside a function.**

## What Claude should help with

- Architecture decisions (federation protocol design; the web framework and DB are settled — Django + PostgreSQL)
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

See **[Where things stand](#where-things-stand--read-this-first)** at the top of this file, and `docs/roadmap.md` for the full slice table. Don't duplicate slice status here — it goes stale, which is exactly what happened to this section before.
