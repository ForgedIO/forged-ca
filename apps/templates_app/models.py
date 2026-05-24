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
    # ── TLS / Web servers ──────────────────────────────────────────────
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
    "radius_server": {
        "label": "RADIUS server (EAP-TLS — NPS / FreeRADIUS / Cisco ISE / ClearPass)",
        "eku":   ["serverAuth"],
        "ku":    ["digitalSignature", "keyEncipherment"],
    },
    "guest_portal": {
        "label": "Guest / captive portal (Cisco ISE, Aruba ClearPass, Meraki, FortiGate)",
        "eku":   ["serverAuth", "clientAuth"],
        "ku":    ["digitalSignature", "keyEncipherment"],
    },
    "server_to_server_mtls": {
        "label": "Server-to-server mutual TLS (Cisco pxGrid, service mesh, internal API)",
        "eku":   ["serverAuth", "clientAuth"],
        "ku":    ["digitalSignature", "keyEncipherment"],
    },

    # ── Identity / Authentication ──────────────────────────────────────
    "client_auth": {
        "label": "Client authentication (mTLS / 802.1X supplicant / API client)",
        "eku":   ["clientAuth"],
        "ku":    ["digitalSignature", "keyAgreement"],
    },
    "smartcard_logon": {
        "label": "Smart card logon — Microsoft AD (also covers 802.1X EAP-TLS)",
        "eku":   ["clientAuth", "msSmartcardLogon"],
        "ku":    ["digitalSignature", "keyEncipherment"],
    },

    # ── Code & Email ───────────────────────────────────────────────────
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

    # ── VPN / IPsec ────────────────────────────────────────────────────
    "vpn_server_ikev2": {
        "label": "VPN server / IKEv2 gateway (StrongSwan, libreswan, Cisco ASA)",
        "eku":   ["serverAuth", "ipsecIKE"],
        "ku":    ["digitalSignature", "keyEncipherment", "keyAgreement"],
    },
    "vpn_client_ikev2": {
        "label": "VPN client / IKEv2 (remote-access workstation)",
        "eku":   ["clientAuth", "ipsecIKE"],
        "ku":    ["digitalSignature", "keyAgreement"],
    },
    "ipsec_endpoint": {
        "label": "IPsec site-to-site peer (no server/client role distinction)",
        "eku":   ["ipsecIKE"],
        "ku":    ["digitalSignature", "keyAgreement"],
    },

    # ── Special purpose (exclusive EKUs) ───────────────────────────────
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


# Optgroup layout for the dropdown — keeps the long list scannable by
# clustering related use cases. The flat USE_CASE_PRESETS dict above is
# still the JS autofill source of truth; this list only controls visual
# grouping in the form's <select>.
USE_CASE_GROUPS = [
    ("TLS / Web servers",     ["web_server", "tls_server_only", "radius_server", "guest_portal", "server_to_server_mtls"]),
    ("Identity / Auth",       ["client_auth", "smartcard_logon"]),
    ("Code & Email",          ["code_signing", "email_smime"]),
    ("VPN / IPsec",           ["vpn_server_ikev2", "vpn_client_ikev2", "ipsec_endpoint"]),
    ("Special purpose",       ["ocsp_responder", "tsa"]),
]


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
                  "'clientAuth'). Enforced at issuance — step-ca writes "
                  "exactly these EKU bits on every cert it issues against "
                  "any provisioner bound to this template, regardless of "
                  "what the CSR requests.",
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

    def to_step_ca_x509_template(self) -> str:
        """Render the step-ca x509 certificate template that pins this
        template's EKU + KU on every cert issued through any provisioner
        bound to it.

        step-ca evaluates this string per issuance: `.Subject` and `.SANs`
        come from the CSR (so the issued cert still reflects what the
        client asked for), but keyUsage and extKeyUsage are hardcoded —
        the CA writes the template's allowlist regardless of what the CSR
        requested. That's the enforcement: a misbehaving client can't
        sneak codeSigning into a "web server" template.

        Custom OIDs land in extKeyUsage alongside the named ones; step-ca
        accepts both dotted-OID strings and named shortcuts in the same
        array. If both lists are empty (template hasn't been edited),
        emit a minimal template that just forwards Subject + SANs — step-ca
        will fall back to its own defaults.
        """
        import json as _json

        ekus = list(self.extended_key_usages) + list(self.custom_eku_oids)
        kus = list(self.key_usages)

        parts = [
            '"subject": {{ toJson .Subject }}',
            '"sans": {{ toJson .SANs }}',
        ]
        if kus:
            parts.append(f'"keyUsage": {_json.dumps(kus)}')
        if ekus:
            parts.append(f'"extKeyUsage": {_json.dumps(ekus)}')

        return "{\n  " + ",\n  ".join(parts) + "\n}"

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
