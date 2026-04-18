import django.db.models.deletion
import encrypted_model_fields.fields
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MFAConfig",
            fields=[
                ("id", models.PositiveSmallIntegerField(default=1, primary_key=True, serialize=False)),
                ("enforce_mfa", models.BooleanField(default=True, help_text="Require all local/LDAP/SAML/OIDC users to set up MFA.")),
            ],
            options={
                "verbose_name": "MFA configuration",
            },
        ),
        migrations.CreateModel(
            name="UserProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("must_change_password", models.BooleanField(default=False, help_text="Force the user to set a new password on next login.")),
                (
                    "auth_source",
                    models.CharField(
                        choices=[
                            ("local", "Local"),
                            ("ldap", "LDAP"),
                            ("entra", "Entra ID"),
                            ("saml", "Generic SAML"),
                            ("oidc", "Generic OIDC"),
                        ],
                        default="local",
                        max_length=20,
                    ),
                ),
                ("mfa_enabled", models.BooleanField(default=False)),
                ("mfa_secret", encrypted_model_fields.fields.EncryptedCharField(blank=True, default="", max_length=64)),
                ("mfa_recovery_codes", encrypted_model_fields.fields.EncryptedCharField(blank=True, default="", max_length=500)),
                ("mfa_confirmed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="profile",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
