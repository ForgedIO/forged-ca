from django.contrib import admin

from .models import ACMEProvisioner


@admin.register(ACMEProvisioner)
class ACMEProvisionerAdmin(admin.ModelAdmin):
    list_display = ("name", "enabled", "default_leaf_lifetime_hours", "updated_at")
