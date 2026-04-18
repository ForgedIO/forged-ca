import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="NodeConfig",
            fields=[
                ("id", models.PositiveSmallIntegerField(default=1, primary_key=True, serialize=False)),
                ("is_root", models.BooleanField(default=False)),
                ("is_intermediate", models.BooleanField(default=False)),
                ("is_issuing", models.BooleanField(default=False)),
                ("wizard_step", models.PositiveSmallIntegerField(default=1)),
                ("is_configured", models.BooleanField(default=False)),
                ("fleet_uuid", models.UUIDField(default=uuid.uuid4, editable=False)),
                ("hostname", models.CharField(blank=True, max_length=255)),
                ("root_lifetime_days", models.PositiveIntegerField(default=7300)),
                ("intermediate_lifetime_days", models.PositiveIntegerField(default=3650)),
                ("issuing_lifetime_days", models.PositiveIntegerField(default=1825)),
                ("root_cn", models.CharField(default="ForgedCA Root CA", max_length=255)),
                ("intermediate_cn", models.CharField(default="ForgedCA Intermediate CA", max_length=255)),
                ("issuing_cn", models.CharField(default="ForgedCA Issuing CA", max_length=255)),
                ("org", models.CharField(default="ForgedCA", max_length=255)),
                ("root_cert_path", models.CharField(blank=True, max_length=500)),
                ("root_key_path", models.CharField(blank=True, max_length=500)),
                ("intermediate_cert_path", models.CharField(blank=True, max_length=500)),
                ("intermediate_key_path", models.CharField(blank=True, max_length=500)),
                ("issuing_cert_path", models.CharField(blank=True, max_length=500)),
                ("issuing_key_path", models.CharField(blank=True, max_length=500)),
                ("trust_download_requires_auth", models.BooleanField(default=False)),
                ("default_acme_provisioner", models.CharField(default="forgedca-acme", max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("configured_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "verbose_name": "Node configuration",
            },
        ),
    ]
