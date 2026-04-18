from django.contrib.auth import get_user_model
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from encrypted_model_fields.fields import EncryptedCharField


class UserProfile(models.Model):
    """One-to-one extension of the built-in User model."""

    AUTH_SOURCE_LOCAL = "local"
    AUTH_SOURCE_LDAP = "ldap"
    AUTH_SOURCE_ENTRA = "entra"
    AUTH_SOURCE_SAML = "saml"
    AUTH_SOURCE_OIDC = "oidc"
    AUTH_SOURCE_CHOICES = [
        (AUTH_SOURCE_LOCAL, "Local"),
        (AUTH_SOURCE_LDAP, "LDAP"),
        (AUTH_SOURCE_ENTRA, "Entra ID"),
        (AUTH_SOURCE_SAML, "Generic SAML"),
        (AUTH_SOURCE_OIDC, "Generic OIDC"),
    ]

    user = models.OneToOneField(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="profile",
    )
    must_change_password = models.BooleanField(
        default=False,
        help_text="Force the user to set a new password on next login.",
    )
    auth_source = models.CharField(
        max_length=20,
        choices=AUTH_SOURCE_CHOICES,
        default=AUTH_SOURCE_LOCAL,
    )

    mfa_enabled = models.BooleanField(default=False)
    mfa_secret = EncryptedCharField(max_length=64, blank=True, default="")
    mfa_recovery_codes = EncryptedCharField(max_length=500, blank=True, default="")
    mfa_confirmed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Profile({self.user.username})"

    @property
    def needs_mfa_at_login(self) -> bool:
        """TOTP MFA applies to everyone except IdPs that bring their own MFA
        (Entra, Duo-layered). Slice 1.5 ships local/LDAP/SAML/OIDC TOTP."""
        return self.auth_source != self.AUTH_SOURCE_ENTRA


class MFAConfig(models.Model):
    """Singleton: global MFA enforcement setting."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    enforce_mfa = models.BooleanField(
        default=True,
        help_text="Require all local/LDAP/SAML/OIDC users to set up MFA.",
    )

    class Meta:
        verbose_name = "MFA configuration"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> "MFAConfig":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


@receiver(post_save, sender=get_user_model())
def _create_user_profile(sender, instance, created, **kwargs):
    """Auto-create a UserProfile whenever a new User is saved."""
    if created:
        UserProfile.objects.get_or_create(user=instance)
