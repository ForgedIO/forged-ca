"""Certificate signing utilities.

Wraps the ``step certificate sign`` CLI (step-ca >= 0.30).

CLI contract (verified against step 0.30.2 on this node):

    step certificate sign <csr-file> <issuing-crt> <issuing-key> \
        [--password-file <file>] [--not-after <duration>] \
        [--template <file> | --profile <name>]

* The three positional args are the CSR, the **issuing CA certificate**, and
  the **issuing CA key**. The signed certificate is written to **stdout**
  (there is no "output file" positional in 0.30).
* The CA key is encrypted at rest, so step needs the passphrase via
  ``--password-file`` — otherwise it would prompt on /dev/tty, which fails
  under gunicorn. The password file lives next to the key
  (``$STEP_PATH/secrets/password.txt``).
* For policy-controlled signing we pass a Go template (``--template``). The
  template's ``subject``/``sans`` are taken from the CSR with
  ``{{ toJson .Subject }}`` / ``{{ toJson .SANs }}``; the policy (keyUsage,
  extKeyUsage, basicConstraints) is embedded literally. ``{{ .CN }}`` /
  ``{{ .SANs }}`` as *bare strings* do NOT work — step unmarshals the rendered
  JSON and expects a proper subject object / SAN array, which the ``toJson``
  helpers produce.
* For passthrough signing we use ``--profile csr`` so step copies the CSR's
  own subject, SANs and extensions verbatim (no policy template).

``--profile`` is mutually exclusive with ``--template``.
"""
import json
import tempfile
import subprocess
from pathlib import Path
from datetime import datetime

from cryptography import x509
from cryptography.x509.oid import NameOID

from apps.issuance.helpers.csr import EKU_OID_TO_SHORT
from apps.nodes.models import NodeConfig

# Default lifetime (days) for passthrough signing when no template is selected.
DEFAULT_LIFETIME_DAYS = 90


class SignerError(Exception):
    pass


def _password_file_path(ca_key_path: str) -> str:
    """step stores the CA key passphrase next to the key in secrets/password.txt."""
    return str(Path(ca_key_path).parent / "password.txt")


def get_ca_paths() -> tuple[str, str, str]:
    """Get the issuing CA cert/key paths from NodeConfig.

    Returns:
        Tuple of (cert_path, key_path, tier)

    Raises:
        SignerError: If no CA role with configured paths is available.
    """
    config = NodeConfig.load()

    if config.is_issuing and config.issuing_cert_path and config.issuing_key_path:
        return (config.issuing_cert_path, config.issuing_key_path, "issuing")
    if config.is_intermediate and config.intermediate_cert_path and config.intermediate_key_path:
        return (config.intermediate_cert_path, config.intermediate_key_path, "intermediate")
    if config.is_root and config.root_cert_path and config.root_key_path:
        return (config.root_cert_path, config.root_key_path, "root")
    raise SignerError("No CA role configured. Cannot sign certificates.")


def _resolve_lifetime_days(template, is_passthrough, requested_lifetime_days):
    """Decide the certificate lifetime, clamped to the template and CA expiry.

    Returns (lifetime_days, was_capped).
    """
    # Determine base lifetime from the template, or the default for passthrough.
    if requested_lifetime_days is not None:
        lifetime_days = requested_lifetime_days
    elif template is not None and getattr(template, "default_lifetime_days", None):
        lifetime_days = template.default_lifetime_days
    else:
        lifetime_days = DEFAULT_LIFETIME_DAYS

    # Clamp to template min/max when a template is present.
    if template is not None:
        if getattr(template, "min_lifetime_days", None):
            lifetime_days = max(lifetime_days, template.min_lifetime_days)
        if getattr(template, "max_lifetime_days", None):
            lifetime_days = min(lifetime_days, template.max_lifetime_days)
    else:
        lifetime_days = max(1, lifetime_days)

    # Cap at the CA's remaining lifetime (1-day safety margin).
    try:
        ca_cert_path, _, _ = get_ca_paths()
        with open(ca_cert_path, "r") as f:
            ca_cert = x509.load_pem_x509_certificate(f.read().encode("utf-8"))
        ca_not_after = ca_cert.not_valid_after_utc
        days_until_expiry = (ca_not_after - datetime.now(ca_not_after.tzinfo)).days
    except Exception:
        # If we can't read the CA cert, trust the requested lifetime; the CA
        # itself will refuse a cert past its own expiry.
        return lifetime_days, False

    if days_until_expiry - 1 < lifetime_days:
        return max(1, days_until_expiry - 1), True
    return lifetime_days, False


def _build_step_template(template) -> str:
    """Build the Go template file contents for policy-controlled signing.

    Subject and SANs come from the CSR (``toJson .Subject`` / ``toJson .SANs``);
    the policy (keyUsage, extKeyUsage) is the template's literal list.
    """
    ekus = list(template.extended_key_usages) if getattr(template, "extended_key_usages", None) else []
    if not ekus:
        ekus = ["serverAuth"]
    kus = list(template.key_usages) if getattr(template, "key_usages", None) else []
    if not kus:
        kus = ["digitalSignature", "keyEncipherment"]

    return (
        "{\n"
        '  "subject": {{ toJson .Subject }},\n'
        '  "sans": {{ toJson .SANs }},\n'
        f'  "keyUsage": {json.dumps(kus)},\n'
        f'  "extKeyUsage": {json.dumps(ekus)},\n'
        '  "basicConstraints": {"isCA": false},\n'
        '  "maxPathLen": 0\n'
        "}\n"
    )


def sign_csr(csr_pem: str, template, is_passthrough: bool = False,
             requested_lifetime_days: int = None) -> tuple[str, dict]:
    """Sign a CSR using ``step certificate sign``.

    Args:
        csr_pem: CSR in PEM format.
        template: CertTemplate instance (may be None for passthrough).
        is_passthrough: If True, bypass template policy and copy the CSR's
            own subject/SAN/extensions (``--profile csr``).
        requested_lifetime_days: Optional override for certificate lifetime.

    Returns:
        Tuple of (signed_certificate_pem, metadata_dict).

    Raises:
        SignerError: If signing fails or the node is not configured.
    """
    if not csr_pem or not csr_pem.strip():
        raise SignerError("Empty CSR provided. Please paste or upload a valid CSR.")

    if not is_passthrough and template is None:
        raise SignerError("No template specified. Please select a certificate template.")

    # Get CA configuration (issuing cert/key + tier).
    ca_cert_path, ca_key_path, signer_tier = get_ca_paths()

    # Determine certificate lifetime (clamped to template + CA expiry).
    lifetime_days, was_capped = _resolve_lifetime_days(
        template, is_passthrough, requested_lifetime_days
    )

    password_file = _password_file_path(ca_key_path)
    not_after = f"{lifetime_days * 24}h"

    # Create temporary directory for files
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # Write CSR to temp file
        csr_file = tmp_path / "csr.pem"
        with open(csr_file, "w") as f:
            f.write(csr_pem)

        # Build the step command.
        cmd = [
            "step", "certificate", "sign",
            str(csr_file),
            ca_cert_path,
            ca_key_path,
            "--password-file", password_file,
            "--not-after", not_after,
        ]

        if is_passthrough:
            # Copy the CSR's own subject/SAN/extensions verbatim.
            cmd += ["--profile", "csr"]
        else:
            template_file = tmp_path / "template.json"
            with open(template_file, "w") as f:
                f.write(_build_step_template(template))
            cmd += ["--template", str(template_file)]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            raise SignerError("Certificate signing timed out after 60 seconds")
        except FileNotFoundError:
            raise SignerError("step CLI not found. Please install step-cli.")

        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or "Unknown error"
            raise SignerError(f"Certificate signing failed: {error_msg}")

        # The signed certificate comes back on stdout.
        cert_pem = result.stdout.strip()
        if not cert_pem.startswith("-----BEGIN CERTIFICATE-----"):
            raise SignerError(
                f"step certificate sign did not return a certificate. "
                f"Output: {result.stdout[:200]!r}"
            )

        signed_cert = x509.load_pem_x509_certificate(cert_pem.encode("utf-8"))

        metadata = {
            "serial": format(signed_cert.serial_number, "X"),
            "common_name": _get_cn_from_cert(signed_cert),
            "sans": _get_sans_from_cert(signed_cert),
            "template_name": template.name if template is not None else ("Passthrough" if is_passthrough else ""),
            "is_passthrough": is_passthrough,
            "extended_key_usages": _get_cert_ekus(signed_cert),
            "key_usages": _get_cert_kus(signed_cert),
            "not_before": signed_cert.not_valid_before_utc,
            "not_after": signed_cert.not_valid_after_utc,
            "signer_tier": signer_tier,
            "was_lifetime_capped": was_capped,
            "signed_lifetime_days": lifetime_days,
        }

        return cert_pem, metadata


def _get_cn_from_cert(cert: x509.Certificate) -> str:
    """Extract Common Name from certificate."""
    try:
        cn_attrs = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        if cn_attrs:
            return cn_attrs[0].value
    except Exception:
        pass
    return ""


def _get_sans_from_cert(cert: x509.Certificate) -> list:
    """Extract Subject Alternative Names from certificate."""
    sans = []
    try:
        san_ext = cert.extensions.get_extension_for_oid(
            x509.oid.ExtensionOID.SUBJECT_ALTERNATIVE_NAME
        )
        for name in san_ext.value:
            if isinstance(name, x509.DNSName):
                sans.append(name.value)
            elif isinstance(name, x509.IPAddress):
                sans.append(str(name.value))
    except x509.ExtensionNotFound:
        pass
    return sans


def _get_cert_ekus(cert: x509.Certificate) -> list:
    """Extract Extended Key Usages from certificate as short names.

    Known OIDs map to the ForgedCA short names (matching ``ParsedCsr`` and
    the template storage); unknown OIDs are kept in dotted form.
    """
    ekus = []
    try:
        eku_ext = cert.extensions.get_extension_for_oid(
            x509.oid.ExtensionOID.EXTENDED_KEY_USAGE
        )
        for eku in eku_ext.value:
            ekus.append(EKU_OID_TO_SHORT.get(eku, eku.dotted_string))
    except x509.ExtensionNotFound:
        pass
    return ekus


def _get_cert_kus(cert: x509.Certificate) -> list:
    """Extract Key Usages from certificate as step short-names."""
    kus = []
    try:
        ku_ext = cert.extensions.get_extension_for_oid(
            x509.oid.ExtensionOID.KEY_USAGE
        )
        ku_value = ku_ext.value
        ku_map = {
            "digital_signature": "digitalSignature",
            "content_commitment": "contentCommitment",
            "key_encipherment": "keyEncipherment",
            "data_encipherment": "dataEncipherment",
            "key_agreement": "keyAgreement",
            "key_cert_sign": "keyCertSign",
            "crl_sign": "cRLSign",
        }
        for attr, name in ku_map.items():
            if getattr(ku_value, attr, False):
                kus.append(name)
    except x509.ExtensionNotFound:
        pass
    return kus
