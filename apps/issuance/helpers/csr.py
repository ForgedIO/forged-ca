"""CSR parsing utilities for Slice 4."""

import logging
from dataclasses import dataclass
from typing import Optional

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import dsa, ec, ed25519, rsa, padding
from cryptography.hazmat.primitives.asymmetric.ec import SECP256R1, SECP384R1
from cryptography.x509.oid import ExtensionOID, NameOID, ExtendedKeyUsageOID

logger = logging.getLogger(__name__)


# EKU short name to OID mapping
EKU_SHORT_TO_OID = {
    "serverAuth": ExtendedKeyUsageOID.SERVER_AUTH,
    "clientAuth": ExtendedKeyUsageOID.CLIENT_AUTH,
    "codeSigning": ExtendedKeyUsageOID.CODE_SIGNING,
    "emailProtection": ExtendedKeyUsageOID.EMAIL_PROTECTION,
    "timeStamping": ExtendedKeyUsageOID.TIME_STAMPING,
    "OCSPSigning": ExtendedKeyUsageOID.OCSP_SIGNING,
    "msSmartcardLogon": x509.oid.ObjectIdentifier("1.3.6.1.4.1.311.20.2.2"),
    "ipsecIKE": x509.oid.ObjectIdentifier("1.3.6.1.5.5.7.3.17"),
}

# OID to short name mapping
EKU_OID_TO_SHORT = {v: k for k, v in EKU_SHORT_TO_OID.items()}

# Key usage bits mapping (short name -> boolean attribute on KeyUsage)
KEY_USAGE_BITS = {
    "digitalSignature": "digital_signature",
    "contentCommitment": "content_commitment",
    "keyEncipherment": "key_encipherment",
    "dataEncipherment": "data_encipherment",
    "keyAgreement": "key_agreement",
    "keyCertSign": "key_cert_sign",
    "cRLSign": "crl_sign",
}


class CsrError(Exception):
    """Raised when CSR parsing fails with a user-readable message."""
    pass


@dataclass
class ParsedCsr:
    """Parsed CSR with all relevant information."""
    common_name: str
    sans: list[str]             # DNS + IP, as strings
    key_type: str               # "RSA" / "EC" / "Ed25519"
    key_size: Optional[int]     # bits for RSA/EC, None for Ed25519
    signature_algorithm: str
    requested_ekus: list[str]   # our short names; unmapped OIDs kept dotted
    requested_kus: list[str]    # our short names
    pem: str                    # normalised PEM


def _normalize_csr_pem(pem: str) -> str:
    """Normalize PEM formatting to ensure consistent comparison."""
    pem = pem.strip()
    if not pem.endswith("\n"):
        pem += "\n"
    return pem


def _parse_key_usage(ku_ext: x509.KeyUsage) -> list[str]:
    """Convert KeyUsage extension to list of short names."""
    kus = []
    if ku_ext.digital_signature:
        kus.append("digitalSignature")
    if ku_ext.content_commitment:
        kus.append("contentCommitment")
    if ku_ext.key_encipherment:
        kus.append("keyEncipherment")
    if ku_ext.data_encipherment:
        kus.append("dataEncipherment")
    if ku_ext.key_agreement:
        kus.append("keyAgreement")
    # CA-only bits - we reject these for leaf certs
    if ku_ext.key_cert_sign:
        kus.append("keyCertSign")
    if ku_ext.crl_sign:
        kus.append("cRLSign")
    return kus


def _parse_extended_key_usage(eku_ext: x509.ExtendedKeyUsage) -> list[str]:
    """Convert ExtendedKeyUsage extension to list of short names."""
    ekus = []
    for oid in eku_ext:
        if oid in EKU_OID_TO_SHORT:
            ekus.append(EKU_OID_TO_SHORT[oid])
        else:
            # Keep OIDs that don't have short names in dotted form
            ekus.append(oid.dotted_string)
    return ekus


def parse_csr(pem: str) -> ParsedCsr:
    """Parse a CSR PEM string into a ParsedCsr dataclass.
    
    Validates the CSR's self-signature and extracts all information.
    
    Args:
        pem: CSR in PEM format
        
    Returns:
        ParsedCsr with all CSR information
        
    Raises:
        CsrError: If parsing fails with a user-readable message
    """
    pem = pem.strip()
    
    # Check for basic PEM structure
    if not pem.startswith("-----BEGIN CERTIFICATE REQUEST-----"):
        if "-----BEGIN CERTIFICATE-----" in pem:
            raise CsrError("This appears to be a certificate, not a CSR. Please paste a CSR.")
        if "-----BEGIN PUBLIC KEY-----" in pem:
            raise CsrError("This appears to be a public key, not a CSR. Please paste a CSR.")
        raise CsrError("Invalid CSR format. Expected PEM with '-----BEGIN CERTIFICATE REQUEST-----'.")
    
    try:
        # Load the CSR
        logger.debug(f"Attempting to load CSR: first 50 chars = {repr(pem[:50])}, length = {len(pem)}")
        csr = x509.load_pem_x509_csr(pem.encode("utf-8"))
    except ValueError as e:
        raise CsrError(f"Could not parse CSR: {str(e)}")
    except Exception as e:
        raise CsrError(f"Failed to parse CSR: {str(e)}")
    
    # Verify the CSR signature
    # NOTE: in cryptography >= 42.0 is_signature_valid is a *property* (bool),
    # not a method. Do not call it with a key argument.
    try:
        if not csr.is_signature_valid:
            raise CsrError("CSR signature is invalid. The CSR may be corrupted or malformed.")
    except CsrError:
        raise
    except Exception as e:
        raise CsrError(f"CSR signature is invalid. The CSR may be corrupted or malformed.")
    
    # Extract Common Name
    try:
        cn_attr = csr.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        common_name = cn_attr[0].value if cn_attr else ""
    except Exception:
        common_name = ""
    
    # Extract Subject Alternative Names
    sans = []
    try:
        san_ext = csr.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
        for san in san_ext.value:
            if isinstance(san, x509.DNSName):
                sans.append(san.value)
            elif isinstance(san, x509.IPAddress):
                sans.append(str(san.value))
            elif isinstance(san, x509.RFC822Name):
                sans.append(san.value)
            elif isinstance(san, x509.UniformResourceIdentifier):
                sans.append(san.value)
            # Add other types as needed
    except x509.ExtensionNotFound:
        pass  # No SANs is fine
    
    # Extract key information
    public_key = csr.public_key()
    if isinstance(public_key, rsa.RSAPublicKey):
        key_type = "RSA"
        key_size = public_key.key_size
    elif isinstance(public_key, ec.EllipticCurvePublicKey):
        key_type = "EC"
        key_size = public_key.key_size
    elif isinstance(public_key, ed25519.Ed25519PublicKey):
        key_type = "Ed25519"
        key_size = None  # Ed25519 has fixed size
    elif isinstance(public_key, dsa.DSAPublicKey):
        key_type = "DSA"
        key_size = public_key.key_size
    else:
        key_type = "Unknown"
        key_size = None
    
    # Extract signature algorithm
    sig_alg = csr.signature_algorithm_oid
    signature_algorithm = sig_alg.dotted_string
    
    # Extract requested EKUs
    requested_ekus = []
    try:
        eku_ext = csr.extensions.get_extension_for_oid(ExtensionOID.EXTENDED_KEY_USAGE)
        requested_ekus = _parse_extended_key_usage(eku_ext.value)
    except x509.ExtensionNotFound:
        pass  # Empty EKUs is fine
    
    # Extract requested KUs
    requested_kus = []
    try:
        ku_ext = csr.extensions.get_extension_for_oid(ExtensionOID.KEY_USAGE)
        requested_kus = _parse_key_usage(ku_ext.value)
    except x509.ExtensionNotFound:
        pass  # Empty KUs is fine
    
    return ParsedCsr(
        common_name=common_name,
        sans=sans,
        key_type=key_type,
        key_size=key_size,
        signature_algorithm=signature_algorithm,
        requested_ekus=requested_ekus,
        requested_kus=requested_kus,
        pem=_normalize_csr_pem(pem),
    )


def format_eku_for_display(ekus: list[str]) -> str:
    """Format EKUs for user-friendly display."""
    from apps.templates_app.models import EKU_CHOICES, EKU_SHORT_LABELS
    
    labels = []
    for eku in ekus:
        # Try to find the friendly label
        for oid, label in EKU_CHOICES:
            if oid == eku or label.startswith(EKU_SHORT_LABELS.get(eku, eku)):
                labels.append(label)
                break
        else:
            # If not found, show the raw value
            labels.append(eku)
    
    return ", ".join(labels)