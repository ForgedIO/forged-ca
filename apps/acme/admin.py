from django.contrib import admin

from .models import ACMEProvisioner


@admin.register(ACMEProvisioner)
class ACMEProvisionerAdmin(admin.ModelAdmin):
    list_display = ("name", "enabled", "template", "updated_at")
