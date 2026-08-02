---
name: test-forgedca
description: How to test ForgedCA — page-render smoke tests, unit tests for helpers, and headless-browser checks. Use when writing tests, verifying a slice, or checking that pages still render after a change.
---

# Testing ForgedCA

## Why this exists

**20 of ForgedCA's first 79 commits were page-render breakage** — `TemplateSyntaxError:
'block content' appears twice`, leaking Django template comments (twice), a
`/change-password/ ↔ /wizard/` redirect loop, a stray `*/` that closed a CSS block early
and shipped an unstyled UI.

Every one of those would have been caught by a test that visits the page and asserts it
renders. That is the highest-value test in this codebase — write it before anything
clever.

## Tier 1 — smoke test (start here, always)

In-process Django test client. No browser, no running server, no TLS. Runs in seconds.

**Catches:** `TemplateSyntaxError`, `NoReverseMatch` from a bad `{% url %}`, missing
context variables, view import errors, redirect loops, 500s.

**Does not catch:** anything involving JavaScript, HTMX swaps, CSS, or layout. That's
Tier 3.

### Running it

```bash
DJANGO_SETTINGS_MODULE=forgedca.settings.test python3 manage.py test
```

`forgedca/settings/test.py` uses **in-memory SQLite**, so this runs on any dev box.
Don't reach for Postgres — the box you're on probably doesn't have it running, and a
suite nobody can run is worthless.

### The three gates you must clear

This is the part that trips people. Three middleware layers redirect an authenticated
user away from almost every page, in this order (`forgedca/settings/base.py`):

1. `ForcePasswordChangeMiddleware` → `/change-password/` when `user.profile.must_change_password`
2. `ForceMFASetupMiddleware` → `/mfa/setup/` when `not profile.mfa_enabled` and MFA is enforced
3. `WizardRedirectMiddleware` → `wizard:step_role` when the node isn't configured

**Miss any of these and every assertion passes against a 302 to the wizard, proving
nothing.** A smoke test that "passes" while testing zero real pages is worse than no
test, because it buys false confidence.

So the fixture must produce an admin who is fully through onboarding, on a fully
configured node:

```python
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.nodes.models import NodeConfig


class SmokeTestCase(TestCase):
    """Base class for any test that needs to reach a real page."""

    def setUp(self):
        user = get_user_model().objects.create_user("smoke", password="x")
        profile = user.profile
        profile.must_change_password = False
        profile.mfa_enabled = True
        profile.save()

        config = NodeConfig.load()
        config.is_root = True
        config.is_intermediate = True
        config.is_issuing = True
        config.is_configured = True
        config.hostname = "ca.test.local"
        config.save()

        # force_login sets the session directly, so TOTP never enters the
        # picture at this tier.
        self.client.force_login(user)
        self.user = user
        self.config = config
```

Set **all three roles**. Many pages are role-gated on `config.is_issuing` and will
render a "this node doesn't have that role" branch instead of the real content.

Also write at least one test that asserts the gates *work* — an un-onboarded user really
does get redirected. Otherwise a future change that disables the middleware would make
the suite greener, not redder.

### Walking every URL

Enumerate from the urlconf rather than hand-listing paths, so new pages are covered the
day they're added:

```python
from django.urls import get_resolver, URLPattern, URLResolver


def all_named_urls():
    """Every reversible URL that takes no arguments."""
    out = []

    def walk(patterns, prefix=""):
        for p in patterns:
            if isinstance(p, URLResolver):
                walk(p.url_patterns, prefix + str(p.pattern))
            elif isinstance(p, URLPattern) and p.name:
                if not p.pattern.regex.groups:      # skip <int:pk> etc.
                    out.append(prefix + str(p.pattern))
    walk(get_resolver().url_patterns)
    return out
```

Then assert each one returns < 500 and doesn't raise. Skip `/admin/` (Django's own) and
any destructive POST-only endpoint.

Pages needing an object (`<int:pk>/edit/`) get their own tests with a created fixture —
don't try to force them through the generic walker.

## Tier 2 — unit tests for helpers

Logic lives in `apps/<app>/helpers/` (see `CLAUDE.md`). Test those as plain functions —
no client, no DB where avoidable. This is where CSR parsing, policy validation, and
lifetime clamping belong.

Anything that shells out to `step` must sit behind a seam that can be faked. **The
`step` CLI is not installed on every dev box** — it's on the testbed, not necessarily
locally. A test that silently skips when `step` is missing is fine; a test that fails
because of it will get deleted.

Generate certificate and CSR fixtures in code with `cryptography`. **Do not commit
`.pem` / `.crt` / `.key` fixture files** — `.gitignore` blocks them, and a fixture that
can't be committed is worse than none.

## Tier 3 — headless browser

Only after Tiers 1 and 2 pass. Catches what they structurally cannot: JS console errors,
HTMX swap failures, DaisyUI theme contrast, layout breakage. ForgedCA has lost real time
to all four — three separate commits on tab styling alone, plus dark-mode form controls
and oversized icons.

Put these in `tests/e2e/`.

### Two obstacles, both solvable

**TOTP MFA is mandatory.** A headless browser can't `force_login`. But `pyotp` is
already a dependency, so compute a live code from the enrolled secret and drive the real
login form:

```python
import pyotp
code = pyotp.TOTP(profile.totp_secret).now()
```

This is better than a test-only bypass, because it exercises the login path you actually
ship.

**TLS is private-CA or self-signed** on port 8443. Either launch the browser with
certificate errors ignored, or install the node's Root first. Ignoring is fine for a
render check; if you're testing the *trust* story specifically, install the Root — that
is the thing under test.

### What to assert

- HTTP status and that the page has content
- **Browser console is free of errors** — this is the highest-value browser assertion
  and the cheapest to write
- Key elements are present and visible
- Both light and dark themes, if the change touched styling

## Verifying on the testbed

`cday@192.168.1.172` (hostname `RootCA`). Full passwordless sudo.

```bash
ssh cday@192.168.1.172
cd ~/forged-ca && sudo ./update.sh
```

`update.sh` self-pulls from `origin/main`, so **push before deploying** — deploying
doesn't pick up uncommitted local work.

After deploying:

```bash
systemctl is-active step-ca forgedca-gunicorn nginx postgresql
curl -sk -o /dev/null -w "%{http_code}\n" https://localhost:8443/     # 302 → login is correct
journalctl -u step-ca -n 50 --no-pager                                # if step-ca is down
```

**step-ca failing to start after a template change means the rendered x509 template is
malformed.** That's the single most likely way to break this deployment.

Fix in the repo and redeploy. **Never edit files under `/opt/forgedca/` directly** —
`update.sh` overwrites them and the fix vanishes.

## Checklist before calling a slice tested

- [ ] `manage.py test` passes under `forgedca.settings.test`
- [ ] `manage.py makemigrations --check --dry-run` is clean (no model/migration drift)
- [ ] Every new page has a smoke test that asserts a real 200, not a redirect
- [ ] New helper logic has unit tests, including the failure cases
- [ ] Deployed to the testbed and services are still active
- [ ] No internal slice numbers in any new admin-facing copy — 14 were removed in
      `91eebd0`; don't reintroduce them
