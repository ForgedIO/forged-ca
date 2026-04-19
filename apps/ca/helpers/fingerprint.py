"""SHA-256 fingerprint of a PEM-encoded certificate, in lowercase hex.

Matches what step-ca prints at startup ("X.509 Root Fingerprint: …") and
what `step ca bootstrap --fingerprint` expects. Hashed over the DER bytes
of the leaf cert, not the PEM armour.
"""
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes


def cert_sha256(pem_path: str | Path) -> str:
    """Return the SHA-256 fingerprint of the cert at `pem_path` as hex.
    Empty string if the path is missing or unreadable — callers render a
    placeholder rather than crashing the whole page."""
    try:
        data = Path(pem_path).read_bytes()
    except (OSError, TypeError):
        return ""
    try:
        cert = x509.load_pem_x509_certificate(data)
    except ValueError:
        return ""
    return cert.fingerprint(hashes.SHA256()).hex()
