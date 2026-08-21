"""Models for certificate issuance."""
from django.db import models
from django.conf import settings

from apps.templates_app.models import CertTemplate


class IssuedCertificate(models.Model):
    """A certificate that has been issued by ForgedCA."""

    SOURCE_MANUAL = "manual"
    SOURCE_ACME = "acme"
    SOURCE_CHOICES = [
        (SOURCE_MANUAL, "Manual CSR signing"),
        (SOURCE_ACME, "ACME auto-enrollment"),
    ]

    SIGNER_ISSUING = "issuing"
    SIGNER_INTERMEDIATE = "intermediate"
    SIGNER_ROOT = "root"
    SIGNER_CHOICES = [
        (SIGNER_ISSUING, "Issuing CA"),
        (SIGNER_INTERMEDIATE, "Intermediate CA"),
        (SIGNER_ROOT, "Root CA"),
    ]

    serial = models.CharField(
        max_length=64,
        unique=True,
        help_text="Certificate serial number (uppercase hex)",
    )
    common_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Certificate Common Name",
    )
    sans = models.TextField(
        blank=True,
        help_text="Subject Alternative Names (one per line)",
    )
    template = models.ForeignKey(
        CertTemplate,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        help_text="Template used for issuance (null if passthrough or template deleted)",
    )
    template_name = models.CharField(
        max_length=120,
        blank=True,
        help_text="Snapshot of template name at time of issuance (survives template rename/delete)",
    )
    is_passthrough = models.BooleanField(
        default=False,
        help_text="True if passthrough signing was used (bypassed template policy)",
    )
    extended_key_usages = models.JSONField(
        default=list,
        help_text="EKUs that were actually issued",
    )
    key_usages = models.JSONField(
        default=list,
        help_text="KUs that were actually issued",
    )
    not_before = models.DateTimeField(help_text="Certificate validity start")
    not_after = models.DateTimeField(help_text="Certificate validity end")
    signer_tier = models.CharField(
        max_length=16,
        blank=True,
        choices=SIGNER_CHOICES,
        help_text="Which tier signed this certificate",
    )
    source = models.CharField(
        max_length=16,
        choices=SOURCE_CHOICES,
        default=SOURCE_MANUAL,
        help_text="Source of this certificate issuance",
    )
    certificate_pem = models.TextField(help_text="Issued certificate in PEM format")
    csr_pem = models.TextField(
        blank=True,
        help_text="Original CSR in PEM format",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this certificate was issued",
    )
    signed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    # csr field is reserved for future use - currently csr_pem is used instead
    # When we add ACME support, we may link to the ACMEOrder model
    csr = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="issued_certificates",
        help_text="Original CSR that was signed (reserved for future ACME integration)",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "issued certificate"
        verbose_name_plural = "issued certificates"

    def __str__(self):
        return f"{self.common_name or 'Unknown'} ({self.serial[:8]}...)"
