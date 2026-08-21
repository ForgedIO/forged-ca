"""Policy validation for CSR signing."""
from typing import List, Set

from apps.issuance.helpers.csr import ParsedCsr, CsrError, KEY_USAGE_BITS

# CA-only key usages that are never allowed on leaf certificates
CA_KEY_USAGES = {"keyCertSign", "cRLSign"}


class CsrValidationError(Exception):
    pass


def validate_csr_policy(parsed: ParsedCsr, template) -> List[str]:
    """Validate CSR against template. Returns list of rejection reasons."""
    reasons = []
    
    # Get allowed EKUs from template (short names + custom OIDs)
    allowed_ekus = _get_allowed_ekus(template)
    
    # Get allowed KUs from template
    allowed_kus = set(template.key_usages)
    
    # Check for CA key usages (always rejected)
    for ku in parsed.requested_kus:
        if ku in CA_KEY_USAGES:
            reasons.append(f"CA usage ({ku}) is not allowed on leaf certificates")
    
    # Check EKUs
    for eku in parsed.requested_ekus:
        if eku not in allowed_ekus:
            reasons.append(f"Extended Key Usage '{eku}' is not permitted by this template")
    
    # Check KUs
    for ku in parsed.requested_kus:
        if ku not in allowed_kus and ku not in CA_KEY_USAGES:
            reasons.append(f"Key Usage '{ku}' is not permitted by this template")
    
    return reasons


def _get_allowed_ekus(template) -> Set[str]:
    """Get all allowed EKUs from template (short names + custom OIDs)."""
    allowed = set(template.extended_key_usages)
    
    # Add custom EKU OIDs
    if hasattr(template, 'custom_eku_oids') and template.custom_eku_oids:
        allowed.update(template.custom_eku_oids)
    
    return allowed


def format_validation_error(parsed: ParsedCsr, template) -> str:
    """Format validation error message in admin-friendly language."""
    reasons = validate_csr_policy(parsed, template)
    if not reasons:
        return ""
    
    # Get EKU labels for admin-friendly display
    from apps.templates_app.models import EKU_SHORT_LABELS
    
    requested_ekus = []
    for eku in parsed.requested_ekus:
        # Try to get friendly label, fall back to showing the raw value
        label = EKU_SHORT_LABELS.get(eku, eku)
        requested_ekus.append(label)
    
    allowed_ekus = []
    for eku in template.extended_key_usages:
        label = EKU_SHORT_LABELS.get(eku, eku)
        allowed_ekus.append(label)
    
    # Add custom EKUs to allowed list
    if hasattr(template, 'custom_eku_oids') and template.custom_eku_oids:
        allowed_ekus.extend(template.custom_eku_oids)
    
    # Get KU labels
    requested_kus = parsed.requested_kus
    allowed_kus = template.key_usages
    
    # Build the error message
    message_parts = [f"This CSR cannot be signed with the '{template.name}' template."]
    
    if requested_ekus:
        message_parts.append(f"\nRequested EKUs: {', '.join(requested_ekus)}")
        message_parts.append(f"Allowed EKUs: {', '.join(allowed_ekus) if allowed_ekus else 'None'}")
    
    if requested_kus:
        message_parts.append(f"\nRequested KUs: {', '.join(requested_kus)}")
        message_parts.append(f"Allowed KUs: {', '.join(allowed_kus) if allowed_kus else 'None'}")
    
    message_parts.append("\n\nPick a template that includes the requested extensions,")
    message_parts.append("or use passthrough mode if you're sure.")
    
    return "\n".join(message_parts)


def is_ca_key_usage(ku: str) -> bool:
    """Check if a key usage is a CA-only usage."""
    return ku in CA_KEY_USAGES
