from django.db import models


# Friendly EKU choices surfaced in the template builder. Values match the
# OpenSSL / x509 spec short names so they slot directly into step-ca's
# certificate-template renderer when Slice 4 enforcement lands.
EKU_CHOICES = [
    ("serverAuth",       "Server authentication (TLS, web servers, APIs)"),
    ("clientAuth",       "Client authentication (mTLS, VPN, 802.1X)"),
    ("codeSigning",      "Code signing"),
    ("emailProtection",  "Email — S/MIME"),
    ("timeStamping",     "Time stamping"),
    ("OCSPSigning",      "OCSP signing"),
    ("msSmartcardLogon", "Smart card logon (Microsoft AD)"),
    ("ipsecIKE",         "IPsec IKE"),
]

# Friendly KU choices. CA-only bits (keyCertSign, cRLSign) intentionally
# omitted — these templates are for issued leaves, not CA certs.
KU_CHOICES = [
    ("digitalSignature",  "Digital signature"),
    ("contentCommitment", "Content commitment (non-repudiation)"),
    ("keyEncipherment",   "Key encipherment (RSA TLS)"),
    ("dataEncipherment",  "Data encipherment"),
    ("keyAgreement",      "Key agreement (ECDH)"),
]

# Short labels for the index list — keeps the chip column scannable.
EKU_SHORT_LABELS = {
    "serverAuth":       "Server",
    "clientAuth":       "Client",
    "codeSigning":      "Code",
    "emailProtection":  "Email",
    "timeStamping":     "TSA",
    "OCSPSigning":      "OCSP",
    "msSmartcardLogon": "Smartcard",
    "ipsecIKE":         "IPsec",
}

# One-click use-case presets that autofill the right EKU + KU combo for the
# admin. Picking a use case from the dropdown in the form overwrites the
# checkbox state via inline JS. Single source of truth for both the
# dropdown options and the JS autofill payload.
#
# Pairings follow common practice: RSA-friendly KU (digitalSignature +
# keyEncipherment) for TLS, ECDH-friendly KU (digitalSignature +
# keyAgreement) for IPsec / VPN, contentCommitment for time stamping
# (non-repudiation is the whole point of a TSA cert).
USE_CASE_PRESETS = {
    "web_server": {
        "label": "Web server (TLS — server + client auth)",
        "eku":   ["serverAuth", "clientAuth"],
        "ku":    ["digitalSignature", "keyEncipherment"],
    },
    "tls_server_only": {
        "label": "TLS server only (no client auth)",
        "eku":   ["serverAuth"],
        "ku":    ["digitalSignature", "keyEncipherment"],
    },
    "client_auth": {
        "label": "Client authentication (mTLS / VPN / 802.1X)",
        "eku":   ["clientAuth"],
        "ku":    ["digitalSignature", "keyAgreement"],
    },
    "code_signing": {
        "label": "Code signing",
        "eku":   ["codeSigning"],
        "ku":    ["digitalSignature"],
    },
    "email_smime": {
        "label": "Email (S/MIME — sign and encrypt)",
        "eku":   ["emailProtection"],
        "ku":    ["digitalSignature", "keyEncipherment"],
    },
    "smartcard_logon": {
        "label": "Smart card logon (Microsoft AD)",
        "eku":   ["clientAuth", "msSmartcardLogon"],
        "ku":    ["digitalSignature", "keyEncipherment"],
    },
    "ipsec_endpoint": {
        "label": "IPsec endpoint",
        "eku":   ["ipsecIKE"],
        "ku":    ["digitalSignature", "keyAgreement"],
    },
    "ocsp_responder": {
        "label": "OCSP responder (exclusive — RFC 6960)",
        "eku":   ["OCSPSigning"],
        "ku":    ["digitalSignature"],
    },
    "tsa": {
        "label": "Time stamping authority (exclusive — RFC 3161)",
        "eku":   ["timeStamping"],
        "ku":    ["digitalSignature", "contentCommitment"],
    },
}


class CertTemplate(models.Model):
    """Reusable certificate-issuance policy: lifetime bounds plus an EKU/KU
    allowlist (Slice 3.7). Subject DN policy and SAN name-constraints land
    in a later slice.

    Every ACME provisioner (slice 2), SCEP provisioner (slice 3.5), and
    non-ACME signing action (slice 4) references a template. Changing the
    template's defaults propagates to every provisioner bound to it at
    the next render.

    Note on enforcement: the EKU/KU fields are stored and surfaced in the
    UI today, but are not yet enforced at issuance — ACME and SCEP fall
    back to step-ca's per-provisioner defaults until Slice 4 lands the
    step-ca template renderer wiring. Treat them as declared policy
    until then.
    """
    DEFAULT_SLUG = "web-server"

    slug = models.SlugField(
        max_length=63,
        unique=True,
        help_text="Short internal identifier, used in URLs and API calls.",
    )
    name = models.CharField(
        max_length=120,
        help_text="Human-facing name shown on the provisioner picker.",
    )
    description = models.TextField(
        blank=True,
        help_text="Short one-liner telling admins when to pick this template.",
    )
    is_system = models.BooleanField(
        default=False,
        help_text="System templates (the seeded default) can't be deleted — "
                  "they guarantee every provisioner always has a binding.",
    )

    default_lifetime_days = models.PositiveIntegerField(
        default=49,
        help_text="Issued when the client doesn't request a specific duration. "
                  "49 matches CA/B's 2029 public-web ceiling with a small "
                  "margin for renewal crons.",
    )
    min_lifetime_days = models.PositiveIntegerField(
        default=1,
        help_text="Floor the CA will accept. Clients asking for less get "
                  "rejected; most clients ask for 'not-after' so this is "
                  "effectively a safety stop.",
    )
    max_lifetime_days = models.PositiveIntegerField(
        default=825,
        help_text="Ceiling the CA will issue. Clients asking for more get "
                  "silently capped at this value.",
    )

    extended_key_usages = models.JSONField(
        default=list,
        blank=True,
        help_text="What this certificate is allowed to be used for. Stored "
                  "as OpenSSL-style short names (e.g. 'serverAuth', "
                  "'clientAuth'). Enforcement at issuance lands with "
                  "Slice 4 — declared policy only for now.",
    )
    key_usages = models.JSONField(
        default=list,
        blank=True,
        help_text="Low-level Key Usage bits. Usually paired automatically "
                  "with the chosen EKUs — only override if you know why.",
    )
    custom_eku_oids = models.JSONField(
        default=list,
        blank=True,
        help_text="Advanced: extra raw OIDs in dotted notation (e.g. "
                  "1.3.6.1.4.1.311.20.2.2) for EKUs not in the friendly "
                  "list.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "certificate template"
        ordering = ["-is_system", "name"]

    def __str__(self):
        return self.name

    @property
    def default_lifetime_hours(self) -> int:
        return self.default_lifetime_days * 24

    @property
    def min_lifetime_hours(self) -> int:
        return self.min_lifetime_days * 24

    @property
    def max_lifetime_hours(self) -> int:
        return self.max_lifetime_days * 24

    @property
    def eku_short_labels(self) -> list[str]:
        """Short EKU labels for chip rendering in the index list. Includes
        custom OIDs verbatim so admins can spot non-standard policy."""
        labels = [EKU_SHORT_LABELS.get(e, e) for e in self.extended_key_usages]
        labels.extend(self.custom_eku_oids)
        return labels

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.default_lifetime_days < self.min_lifetime_days:
            raise ValidationError("Default lifetime cannot be less than the minimum.")
        if self.default_lifetime_days > self.max_lifetime_days:
            raise ValidationError("Default lifetime cannot exceed the maximum.")
        if self.min_lifetime_days > self.max_lifetime_days:
            raise ValidationError("Minimum cannot exceed maximum.")

    @classmethod
    def load_default(cls) -> "CertTemplate":
        """Return the seeded Web Server template, creating it if missing.
        Called on first ACMEProvisioner.load() so bootstrap is idempotent."""
        obj, _ = cls.objects.get_or_create(
            slug=cls.DEFAULT_SLUG,
            defaults={
                "name": "Web Server (Server + Client Auth)",
                "description": (
                    "Out-of-the-box default for ACME-enrolled web servers. "
                    "Matches how Let's Encrypt and most public CAs issue "
                    "leaves today — serverAuth + clientAuth EKUs, 49-day "
                    "lifetime."
                ),
                "is_system": True,
                "default_lifetime_days": 49,
                "min_lifetime_days": 1,
                "max_lifetime_days": 825,
                "extended_key_usages": ["serverAuth", "clientAuth"],
                "key_usages": ["digitalSignature", "keyEncipherment"],
                "custom_eku_oids": [],
            },
        )
        return obj
