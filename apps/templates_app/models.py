from django.db import models


class CertTemplate(models.Model):
    """Reusable certificate-issuance policy — today: lifetime bounds; later
    slices extend with EKU/KU allowlists, subject DN policy, and SAN
    name-constraints.

    Every ACME provisioner (slice 2) and every non-ACME signing action
    (slice 4) references a template. Changing the template's defaults
    propagates to every provisioner bound to it at the next render.
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
            },
        )
        return obj
