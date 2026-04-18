"""Render /etc/step-ca/ca.json from the current NodeConfig.

Slice 1: the renderer writes ca.json but does *not* start the step-ca
daemon — that (plus provisioner configuration) arrives in slice 2. The
file is still written so operators can inspect what will be served.
"""
import json
import os
from pathlib import Path

from django.conf import settings


def render(config) -> dict | None:
    """Build the ca.json dict for this node, or None if step-ca shouldn't run.

    step-ca serves ACME / JWK / etc. from an Issuing tier; a pure Root or
    Root+Intermediate node has no public API and shouldn't run step-ca.
    """
    if not config.is_issuing:
        return None

    base = Path(settings.STEP_CA_CONFIG_DIR)
    step_db = settings.STEP_CA_DB

    return {
        "root": config.root_cert_path,
        "federatedRoots": [],
        "crt": config.issuing_cert_path,
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
            # Provisioners are intentionally empty in slice 1. The ACME
            # provisioner + default "Web Server" template land in slice 2.
            "provisioners": [],
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
