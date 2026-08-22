"""Certificate signing utilities."""
import tempfile
import subprocess
import os
from pathlib import Path
from datetime import datetime, timedelta

from cryptography import x509
from cryptography.x509.oid import NameOID

from apps.issuance.helpers.csr import ParsedCsr
from apps.nodes.models import NodeConfig


class SignerError(Exception):
    pass


def sign_csr(csr_pem: str, template, is_passthrough: bool = False, 
             requested_lifetime_days: int = None) -> tuple[str, dict]:
    """Sign a CSR using step certificate sign.
    
    Args:
        csr_pem: CSR in PEM format
        template: CertTemplate instance to use for signing
        is_passthrough: If True, bypass template policy and use CSR's requested extensions
        requested_lifetime_days: Optional override for certificate lifetime
        
    Returns:
        Tuple of (signed_certificate_pem, metadata_dict)
        
    Raises:
        SignerError: If signing fails or node is not configured properly
    """
    if not csr_pem or not csr_pem.strip():
        raise SignerError("Empty CSR provided. Please paste or upload a valid CSR.")
    
    if not template:
        raise SignerError("No template specified. Please select a certificate template.")
    
    # Get CA configuration
    ca_cert_path, ca_key_path, signer_tier = get_ca_paths()
    
    # Get the issuing CA's certificate to determine remaining lifetime
    try:
        with open(ca_cert_path, 'r') as f:
            ca_cert_pem = f.read()
        ca_cert = x509.load_pem_x509_certificate(ca_cert_pem.encode('utf-8'))
        ca_not_after = ca_cert.not_valid_after_utc
        days_until_expiry = (ca_not_after - datetime.now(ca_not_after.tzinfo)).days
    except Exception as e:
        raise SignerError(f"Failed to read CA certificate: {e}")
    
    # Determine certificate lifetime
    if requested_lifetime_days is None:
        # Use template default
        lifetime_days = template.default_lifetime_days
    else:
        lifetime_days = requested_lifetime_days
    
    # Clamp to template min/max
    if lifetime_days < template.min_lifetime_days:
        lifetime_days = template.min_lifetime_days
    if lifetime_days > template.max_lifetime_days:
        lifetime_days = template.max_lifetime_days
    
    # Cap at CA remaining lifetime (with 1 day safety margin)
    if days_until_expiry - 1 < lifetime_days:
        lifetime_days = max(1, days_until_expiry - 1)
        # We'll include this info in the metadata
        was_capped = True
    else:
        was_capped = False
    
    # Prepare template JSON for step certificate sign
    template_json = _prepare_template_json(template, is_passthrough, csr_pem)
    
    # Create temporary directory for files
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # Write CSR to temp file
        csr_file = tmp_path / "csr.pem"
        with open(csr_file, 'w') as f:
            f.write(csr_pem)
        
        # Write template to temp file
        template_file = tmp_path / "template.json"
        with open(template_file, 'w') as f:
            import json
            json.dump(template_json, f, indent=2)
        
        # Output certificate file
        cert_file = tmp_path / "cert.pem"
        
        # Password file path
        password_file = "/etc/step-ca/secrets/password.txt"
        
        # Calculate not-after date
        not_after = f"+{lifetime_days * 24}h"
        
        # Build step certificate sign command
        cmd = [
            "step", "certificate", "sign",
            str(csr_file),
            str(cert_file),
            ca_key_path,
            "--template", str(template_file),
            "--password-file", password_file,
            "--not-after", not_after,
            "--force",
        ]
        
        try:
            # Run the command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )
            
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or "Unknown error"
                raise SignerError(f"Certificate signing failed: {error_msg}")
            
            # Read the signed certificate
            with open(cert_file, 'r') as f:
                cert_pem = f.read()
            
            # Extract certificate details from the signed cert
            signed_cert = x509.load_pem_x509_certificate(cert_pem.encode('utf-8'))
            
            # Build metadata
            metadata = {
                'serial': format(signed_cert.serial_number, 'X'),
                'common_name': _get_cn_from_cert(signed_cert),
                'sans': _get_sans_from_cert(signed_cert),
                'template_name': template.name,
                'is_passthrough': is_passthrough,
                'extended_key_usages': _get_cert_ekus(signed_cert),
                'key_usages': _get_cert_kus(signed_cert),
                'not_before': signed_cert.not_valid_before_utc,
                'not_after': signed_cert.not_valid_after_utc,
                'signer_tier': signer_tier,
                'was_lifetime_capped': was_capped,
                'signed_lifetime_days': lifetime_days,
            }
            
            return cert_pem, metadata
            
        except subprocess.TimeoutExpired:
            raise SignerError("Certificate signing timed out after 60 seconds")
        except FileNotFoundError:
            raise SignerError("step CLI not found. Please install step-cli.")
        except Exception as e:
            raise SignerError(f"Unexpected error during signing: {e}")


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
    """Extract Extended Key Usages from certificate."""
    ekus = []
    try:
        eku_ext = cert.extensions.get_extension_for_oid(
            x509.oid.ExtensionOID.EXTENDED_KEY_USAGE
        )
        for eku in eku_ext.value:
            ekus.append(eku.dotted_string)
    except x509.ExtensionNotFound:
        pass
    return ekus


def _get_cert_kus(cert: x509.Certificate) -> list:
    """Extract Key Usages from certificate."""
    kus = []
    try:
        ku_ext = cert.extensions.get_extension_for_oid(
            x509.oid.ExtensionOID.KEY_USAGE
        )
        ku_value = ku_ext.value
        
        # Map bit positions to names
        ku_map = {
            0: "digitalSignature",
            1: "contentCommitment",
            2: "keyEncipherment",
            3: "dataEncipherment",
            4: "keyAgreement",
            5: "keyCertSign",
            6: "cRLSign",
        }
        
        for bit, name in ku_map.items():
            bit_value = 1 << bit
            if hasattr(ku_value, name) and getattr(ku_value, name):
                kus.append(name)
    except x509.ExtensionNotFound:
        pass
    return kus


def _prepare_template_json(template, is_passthrough: bool, csr_pem: str = None) -> dict:
    """Prepare template JSON for step certificate sign.
    
    For passthrough mode, extract EKU/KU from the CSR.
    Otherwise, use the template's policy.
    """
    if is_passthrough and csr_pem:
        # Parse CSR to get requested extensions
        from apps.issuance.helpers.csr import parse_csr, ParsedCsr
        
        try:
            parsed_csr = parse_csr(csr_pem)
            
            # Build template from CSR's requested extensions
            template_data = {
                "subject": "{{ .CN }}",
                "sans": "{{ .SANs }}",
                "keyUsage": ["digitalSignature", "keyEncipherment"],
                "extendedKeyUsage": parsed_csr.requested_ekus if parsed_csr.requested_ekus else ["serverAuth"],
                "basicConstraints": {
                    "isCA": False,
                },
                "maxPathLen": 0,
            }
        except Exception:
            # Fall back to template if parsing fails
            template_data = _build_template_from_policy(template)
    else:
        template_data = _build_template_from_policy(template)
    
    return template_data


def _build_template_from_policy(template) -> dict:
    """Build template JSON from CertTemplate policy."""
    # Map template EKUs to step format
    step_ekus = []
    for eku in template.extended_key_usages:
        step_ekus.append(eku)
    
    # If no EKUs specified, default to serverAuth
    if not step_ekus:
        step_ekus = ["serverAuth"]
    
    # Map template KUs to step format
    step_kus = []
    for ku in template.key_usages:
        step_kus.append(ku)
    
    # Default KUs if none specified
    if not step_kus:
        step_kus = ["digitalSignature", "keyEncipherment"]
    
    return {
        "subject": "{{ .CN }}",
        "sans": "{{ .SANs }}",
        "keyUsage": step_kus,
        "extendedKeyUsage": step_ekus,
        "basicConstraints": {
            "isCA": False,
        },
        "maxPathLen": 0,
    }


def get_ca_paths() -> tuple[str, str, str]:
    """Get CA certificate paths from NodeConfig.
    
    Returns:
        Tuple of (cert_path, key_path, tier)
        
    Raises:
        SignerError: If no CA role is configured
    """
    config = NodeConfig.load()
    
    if config.is_issuing:
        return (
            "/etc/step-ca/certs/issuer_ca.crt",
            "/etc/step-ca/secrets/issuer_ca_key",
            "issuing"
        )
    elif config.is_intermediate:
        return (
            "/etc/step-ca/certs/intermediate_ca.crt",
            "/etc/step-ca/secrets/intermediate_ca_key",
            "intermediate"
        )
    elif config.is_root:
        return (
            "/etc/step-ca/certs/root_ca.crt",
            "/etc/step-ca/secrets/root_ca_key",
            "root"
        )
    else:
        raise SignerError("No CA role configured. Cannot sign certificates.")
