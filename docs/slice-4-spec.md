# Slice 4 — Non-ACME CSR signing

**Status:** not started
**Depends on:** Slice 3 (cert templates), Slice 3.7 (EKU/KU policy)
**Roadmap entry:** `docs/roadmap.md`

## Why this exists

Plenty of things that need a certificate can't speak ACME — load balancers, storage
appliances, older Windows boxes, network gear that predates the protocol. Today the
only way to get a cert out of ForgedCA is ACME, which leaves those devices stranded.

Slice 4 gives the admin a path: the device generates a CSR, the admin pastes it into
ForgedCA, picks a template, and gets a signed certificate back — with the same EKU/KU
policy ACME enforces, and a record kept of what was issued.

**User story:** *"My F5 generated a CSR. I want a cert for it, issued under the same
policy as everything else, without learning how ACME works."*

## Scope

### In

1. CSR intake — paste PEM into a textarea, or upload a `.csr` / `.pem` file
2. CSR inspection — parse and display what the request asks for **before** signing
3. Template selection — choose any `CertTemplate`
4. Policy validation — reject out-of-allowlist requests with a specific, named reason
5. Passthrough opt-in — advanced escape hatch that signs the CSR's own extensions
6. Lifetime resolution — template default, clamped, then capped by the signer's own expiry
7. Signing via `step certificate sign`, reusing the Slice 3.7 template renderer
8. `IssuedCertificate` persistence
9. Certificates page — replace the stub with a real list + detail + PEM download

### Out (explicitly deferred)

- **Revocation** — Slice 7. Do not add revocation fields or UI.
- **Audit log entries** — Slice 7. Use `logging` for now.
- **Ingesting ACME-issued certs** into `IssuedCertificate` — the model has a `source`
  field so this can land later without a schema change, but Slice 4 only writes
  `source="manual"`.
- **Dashboard rollups / expiry charts** — Slice 6.
- **Subject DN policy and SAN name-constraints** — deferred with the rest of 3.7's
  leftovers. Slice 4 validates EKU/KU only.
- **SCEP** — Slice 3.5.

## Architecture

Follow the established per-app layout (see `CLAUDE.md` and the existing
`apps/templates_app/`): one view class per file, thin `get()`/`post()`, real logic in
`helpers/`, **all imports at the top of the file**.

```
apps/issuance/
├── models.py                 # IssuedCertificate
├── forms.py                  # CsrSignForm
├── urls.py
├── helpers/
│   ├── __init__.py
│   ├── csr.py                # parse a CSR into a ParsedCsr dataclass
│   ├── policy.py             # validate ParsedCsr against a CertTemplate
│   └── signer.py             # shell out to `step certificate sign`
├── views/
│   ├── __init__.py           # re-export every view class
│   ├── index.py              # list of issued certificates (replaces the stub)
│   ├── sign.py               # GET form + POST sign
│   ├── detail.py             # one certificate
│   └── download.py           # PEM download (leaf and fullchain)
└── migrations/0001_initial.py

templates/issuance/
├── index.html                # rewrite: real list, not the stub alert
├── sign.html
└── detail.html
```

## Data model — `IssuedCertificate`

| Field | Type | Notes |
|---|---|---|
| `serial` | CharField(64), unique, indexed | Uppercase hex. Slice 7 revokes by this. |
| `common_name` | CharField(255), blank | |
| `sans` | TextField, blank | One per line, as issued |
| `template` | FK → `templates_app.CertTemplate`, null, `SET_NULL` | Null on passthrough or if deleted |
| `template_name` | CharField(120), blank | Snapshot — history survives rename/delete |
| `is_passthrough` | BooleanField | |
| `extended_key_usages` | JSONField(list) | What was **issued**, not what was requested |
| `key_usages` | JSONField(list) | Same |
| `not_before` / `not_after` | DateTimeField | |
| `signer_tier` | CharField(16), blank | `issuing` / `intermediate` / `root` |
| `signed_by` | FK → AUTH_USER_MODEL, null, `SET_NULL` | Record outlives the account |
| `source` | CharField(16), choices | `manual` (Slice 4) or `acme` (later) |
| `certificate_pem` | TextField | So a lost cert can be re-downloaded |
| `csr_pem` | TextField, blank | Shows requested-vs-issued |
| `created_at` | DateTimeField(auto_now_add), indexed | |

`Meta.ordering = ["-created_at"]`.

## CSR parsing — `helpers/csr.py`

Use `cryptography` (already a dependency — do **not** shell out for this). Return a
frozen dataclass:

```python
@dataclass(frozen=True)
class ParsedCsr:
    common_name: str
    sans: list[str]             # DNS + IP, as strings
    key_type: str               # "RSA" / "EC" / "Ed25519"
    key_size: int | None        # bits for RSA/EC, None for Ed25519
    signature_algorithm: str
    requested_ekus: list[str]   # our short names; unmapped OIDs kept dotted
    requested_kus: list[str]    # our short names
    pem: str                    # normalised PEM
```

Raise a `CsrError` with an admin-readable message on: not valid PEM, not a CSR (e.g. a
certificate pasted by mistake — a likely and worth-naming error), or a bad signature.
**Verify the CSR's self-signature** and reject if it fails.

### EKU short name ↔ OID map

`CertTemplate` stores OpenSSL-style short names. Map both directions:

| Short name | OID |
|---|---|
| `serverAuth` | 1.3.6.1.5.5.7.3.1 |
| `clientAuth` | 1.3.6.1.5.5.7.3.2 |
| `codeSigning` | 1.3.6.1.5.5.7.3.3 |
| `emailProtection` | 1.3.6.1.5.5.7.3.4 |
| `timeStamping` | 1.3.6.1.5.5.7.3.8 |
| `OCSPSigning` | 1.3.6.1.5.5.7.3.9 |
| `msSmartcardLogon` | 1.3.6.1.4.1.311.20.2.2 |
| `ipsecIKE` | 1.3.6.1.5.5.7.3.17 |

An OID with no short name stays in dotted form — it must still be shown to the admin
and still be validated against `custom_eku_oids`.

### KU bit ↔ attribute map

`digitalSignature`→`digital_signature`, `contentCommitment`→`content_commitment`,
`keyEncipherment`→`key_encipherment`, `dataEncipherment`→`data_encipherment`,
`keyAgreement`→`key_agreement`. CA-only bits (`keyCertSign`, `cRLSign`) are **never**
issued on a leaf — if a CSR requests them, reject regardless of template.

## Policy validation — `helpers/policy.py`

```python
def validate(parsed: ParsedCsr, template: CertTemplate) -> list[str]:
    """Return a list of admin-readable rejection reasons. Empty list = allowed."""
```

Rules:

1. Every requested EKU must appear in `template.extended_key_usages` **or**
   `template.custom_eku_oids`.
2. Every requested KU must appear in `template.key_usages`.
3. `keyCertSign` / `cRLSign` are always rejected — leaves are not CAs.
4. A CSR requesting **nothing** is fine: the template's policy is applied wholesale.
   This is the common case; do not treat an empty request as an error.

Error copy names both sides, in admin language, not OIDs:

> This CSR requests **Code signing**, which the *Web Server* template doesn't permit.
> That template allows: Server authentication, Client authentication.
> Pick a template that includes Code signing, or use passthrough if you're sure.

Use the friendly labels from `EKU_CHOICES` in the message. An admin should never have
to look up `1.3.6.1.5.5.7.3.3`.

## Passthrough

An advanced, off-by-default checkbox. When on:

- Policy validation is **skipped** (except rule 3 — CA bits are never issued)
- The cert is signed with the **CSR's own** requested EKU/KU, not the template's
- `is_passthrough=True` and `template=None` are recorded
- The UI warns before and labels the result after — a passthrough cert must be
  visually distinct in the list

Rationale: "sign exactly what was asked for" is the honest meaning of the escape
hatch. Falling back to step's default `leaf` profile would silently substitute a
*different* policy, which is worse than either enforcing or passing through.

## Lifetime

In order:

1. Start at `template.default_lifetime_days` (or the admin's override, if the form
   exposes one)
2. Clamp to `[template.min_lifetime_days, template.max_lifetime_days]`
3. **Cap at the signing CA's remaining lifetime**, minus a small safety margin

Step 3 is a hard requirement from `CLAUDE.md`: a leaf must never outlive its issuer.
If the cap actually bites, say so in the UI rather than silently shortening — the
admin needs to know their Issuing CA is near expiry.

## Signing — `helpers/signer.py`

Reuse `CertTemplate.to_step_ca_x509_template()`. Its docstring already commits to
serving this flow, and sharing it means manual and ACME issuance can't drift apart.
For passthrough, render the same JSON shape from the **CSR's** EKU/KU instead.

**Signer selection:** the Issuing CA. If the node has no Issuing role, refuse with
the same reasoning as `apps/ca/views/sign_webui.py` — leaves must not be signed
directly off a Root or Intermediate.

**Verified on the testbed** (step-cli 0.30.2) — these flags exist and are correct:

```
step certificate sign <csr-file> <crt-file> <key-file> \
  --template <rendered-template-file> \
  --password-file /etc/step-ca/secrets/password.txt \
  --not-after <duration> \
  --force
```

Note it is `--password-file`, **not** `--ca-password-file` — `step certificate sign`
takes only one key (the CA's), unlike `step certificate create`.

Paths on a deployed node:

- Issuing cert: `/etc/step-ca/certs/issuer_ca.crt`
- Issuing key: `/etc/step-ca/secrets/issuer_ca_key`
- CA password: `/etc/step-ca/secrets/password.txt`

Write the CSR and rendered template to a temp dir with a tight umask and delete them
in a `finally`. Never write the signed key — there is no key here; the requester keeps
it. That is the whole point of CSR-based issuance and is worth a comment.

Store the **leaf** PEM. Build the fullchain at download time by appending the signer
(+ Intermediate) the way `keygen._webui_chain_paths()` does — the Root is never in the
served chain.

Surface `stderr` from a failed `step` invocation into the error message. A silent
failure here is very hard to debug.

## UI

**`sign.html`** — the flow is two-phase, and the inspection step is the point:

1. Admin pastes/uploads a CSR and submits
2. Page re-renders showing **what the CSR asks for** — CN, SANs, key type/size,
   requested EKU/KU — alongside the template picker
3. Admin picks a template; validation errors appear inline against the request
4. Admin confirms → signed → redirect to detail

Never sign on the first submit. The admin approves something they can see.

**`index.html`** — table: CN, template (or a passthrough badge), issued date, expiry
(with a warning colour when near), serial. Empty state should point at the ACME page,
since ACME is the better path when the device supports it.

**`detail.html`** — full metadata, requested-vs-issued comparison, inline PEM viewer
with copy button, download leaf / download fullchain. Match the existing trust-pane
pattern rather than inventing a new one.

Styling: **CSS-first.** New patterns go in `static/css/app.src.css` under
`@layer components`, not piled into templates as utilities.

## Tests

`tests/` is currently **empty** — there is no suite and nothing runs one. Slice 4
establishes it. Use Django's built-in test runner (`manage.py test`); do not add pytest
without discussing it.

Minimum coverage:

- **`helpers/csr.py`** — valid RSA CSR, valid EC CSR, CSR with SANs, CSR with no
  extensions, a certificate pasted instead of a CSR, malformed PEM, bad signature
- **`helpers/policy.py`** — exact match allowed; subset allowed; superset rejected;
  `keyCertSign` rejected even in passthrough; empty request allowed; custom OID
  allowed when in `custom_eku_oids`
- **Lifetime** — clamps to min and max; caps at signer expiry
- **Model** — `filename_stem` sanitises a CN with a slash or space

Generate CSR fixtures with `cryptography` in a helper rather than committing `.pem`
files — `.gitignore` blocks `*.pem`, and fixtures that can't be committed are worse
than none.

`helpers/signer.py` shells out to `step`, which isn't present on every dev box. Keep
the subprocess call behind a seam so it can be faked in tests, and verify the real
invocation on the testbed.

## Docs

- Tick Slice 4 in `docs/roadmap.md`
- `docs/CHANGELOG.md` entry under `[Unreleased]`
- A help page for the signing flow
- Review all new admin-facing copy: **no internal slice numbers in the UI.** 14 were
  removed in `91eebd0`; don't reintroduce them.

## Acceptance criteria

1. Paste a CSR requesting `serverAuth` → pick Web Server → signs → appears in the list
2. Paste a CSR requesting `codeSigning` → pick Web Server → **rejected**, and the
   message names both Code signing and what the template allows
3. Same CSR + passthrough → signs, `codeSigning` present on the cert, flagged as
   passthrough in the list
4. `openssl x509 -text` on a downloaded cert shows exactly the template's EKU/KU
5. A cert whose requested lifetime exceeds the Issuing CA's remaining life is capped,
   and the UI says so
6. Certificates page lists issued certs; detail re-downloads a valid PEM
7. `manage.py test` passes
8. `manage.py makemigrations --check` is clean

## Testbed

`cday@192.168.1.172` (hostname `RootCA`) — see the project memory entry. Deploy with
`cd ~/forged-ca && sudo ./update.sh`, then verify:

```bash
systemctl status step-ca --no-pager
openssl x509 -in <downloaded.crt> -noout -text | grep -A2 "Extended Key Usage"
```

step-ca refusing to start after a change means the rendered template is malformed —
check `journalctl -u step-ca -n 50`.
