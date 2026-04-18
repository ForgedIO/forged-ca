from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("nodes", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="nodeconfig",
            name="webui_sans",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="nodeconfig",
            name="webui_lifetime_days",
            field=models.PositiveIntegerField(default=365),
        ),
        migrations.AddField(
            model_name="nodeconfig",
            name="webui_cert_path",
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name="nodeconfig",
            name="webui_key_path",
            field=models.CharField(blank=True, max_length=500),
        ),
    ]
