"""Render /etc/step-ca/ca.json from the current NodeConfig.

Slice 1: the renderer writes ca.json but does *not* start the step-ca
daemon — that (plus provisioner configuration) arrives in slice 2. The
file is still written so operators can inspect what will be served.
"""
import json
import os
from pathlib import Path

from django.conf import settings


def _issuer_chain_pem(config) -> Path:
    """Write /etc/step-ca/certs/issuer_chain.crt — the Issuing CA + any
    parent Intermediate CA concatenated, in that order.

    step-ca's `crt` field accepts a PEM bundle. When it signs a leaf, the
    ACME response returns `leaf + the contents of crt[1:]` so the client
    can chain all the way up to its trusted Root without AIA chasing.

    In a 2-tier setup (Root → Intermediate → Leaf) step-ca's single-cert
    `crt` field is fine — the intermediate IS the signer. In a 3-tier
    setup (Root → Intermediate → Issuing → Leaf), pointing `crt` at the
    Issuing cert alone means the Intermediate is missing from the
    returned chain and clients can't validate without pre-trusting it —
    which defeats the whole point of having a Root.
    """
    base = Path(settings.STEP_CA_CONFIG_DIR)
    bundle = base / "certs" / "issuer_chain.crt"
    parts: list[bytes] = []
    if config.issuing_cert_path and Path(config.issuing_cert_path).is_file():
        parts.append(Path(config.issuing_cert_path).read_bytes().rstrip())
    if config.intermediate_cert_path and Path(config.intermediate_cert_path).is_file():
        parts.append(Path(config.intermediate_cert_path).read_bytes().rstrip())
    bundle.write_bytes(b"\n".join(parts) + b"\n")
    os.chmod(bundle, 0o640)
    return bundle


def _provisioners() -> list[dict]:
    """Build the authority.provisioners[] array from model state.

    Kept in this file (rather than models.to_ca_json directly in render())
    so the dependency from renderer → acme is one-way and testable without
    standing up a whole Django-models context.
    """
    # Late import: apps.acme.models pulls in Django models which require
    # settings, and callers import renderer before Django is fully set up in
    # some code paths (install scripts).
    from apps.acme.models import ACMEProvisioner

    try:
        acme = ACMEProvisioner.load()
    except Exception:
        # DB unavailable (fresh install pre-migrate) — render an empty
        # provisioner list so step-ca at least boots.
        return []
    return [acme.to_ca_json()] if acme.enabled else []


def render(config) -> dict | None:
    """Build the ca.json dict for this node, or None if step-ca shouldn't run.

    step-ca serves ACME / JWK / etc. from an Issuing tier; a pure Root or
    Root+Intermediate node has no public API and shouldn't run step-ca.
    """
    if not config.is_issuing:
        return None

    base = Path(settings.STEP_CA_CONFIG_DIR)
    step_db = settings.STEP_CA_DB

    # In a 3-tier setup, `crt` must be the issuer-chain bundle so step-ca
    # includes the Intermediate in the ACME response. _issuer_chain_pem
    # (re)writes the bundle every render — idempotent.
    crt_path = str(_issuer_chain_pem(config))

    return {
        "root": config.root_cert_path,
        "federatedRoots": [],
        "crt": crt_path,
        "key": config.issuing_key_path,
        "address": ":9000",
        "insecureAddress": "",
        "dnsNames": [config.hostname or "localhost"],
        "logger": {"format": "text"},
        "db": {
            "type": "postgresql",
            "dataSource": (
                f"host={step_db['HOST']} port={step_db['PORT']} "
                f"user={step_db['USER']} password={step_db['PASSWORD']} "
                f"dbname={step_db['NAME']} sslmode=disable"
            ),
        },
        "authority": {
            "provisioners": _provisioners(),
        },
        "tls": {
            "cipherSuites": [
                "TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305",
                "TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256",
            ],
            "minVersion": 1.2,
            "maxVersion": 1.3,
            "renegotiation": False,
        },
    }


def write(config) -> Path | None:
    """Render ca.json to /etc/step-ca/ca.json. Returns the path if written,
    or None when the role set doesn't need step-ca."""
    ca = render(config)
    if ca is None:
        return None
    path = Path(settings.STEP_CA_CONFIG_DIR) / "ca.json"
    path.write_text(json.dumps(ca, indent=2))
    os.chmod(path, 0o640)
    return path
