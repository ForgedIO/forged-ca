from django.db import migrations, models


def populate_web_server_defaults(apps, schema_editor):
    """Backfill the seeded Web Server template with the EKU/KU shape its
    description already promises (serverAuth + clientAuth, digitalSignature
    + keyEncipherment). No-op if the template is missing or has already
    been edited by an admin to non-empty values."""
    CertTemplate = apps.get_model("templates_app", "CertTemplate")
    try:
        t = CertTemplate.objects.get(slug="web-server")
    except CertTemplate.DoesNotExist:
        return
    changed = False
    if not t.extended_key_usages:
        t.extended_key_usages = ["serverAuth", "clientAuth"]
        changed = True
    if not t.key_usages:
        t.key_usages = ["digitalSignature", "keyEncipherment"]
        changed = True
    if changed:
        t.save(update_fields=["extended_key_usages", "key_usages"])


class Migration(migrations.Migration):

    dependencies = [
        ("templates_app", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="certtemplate",
            name="extended_key_usages",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text=(
                    "What this certificate is allowed to be used for. Stored "
                    "as OpenSSL-style short names (e.g. 'serverAuth', "
                    "'clientAuth'). Enforcement at issuance lands with "
                    "Slice 4 — declared policy only for now."
                ),
            ),
        ),
        migrations.AddField(
            model_name="certtemplate",
            name="key_usages",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text=(
                    "Low-level Key Usage bits. Usually paired automatically "
                    "with the chosen EKUs — only override if you know why."
                ),
            ),
        ),
        migrations.AddField(
            model_name="certtemplate",
            name="custom_eku_oids",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text=(
                    "Advanced: extra raw OIDs in dotted notation (e.g. "
                    "1.3.6.1.4.1.311.20.2.2) for EKUs not in the friendly "
                    "list."
                ),
            ),
        ),
        migrations.RunPython(populate_web_server_defaults, reverse_code=migrations.RunPython.noop),
    ]
