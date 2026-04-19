from django.contrib import admin

from .models import CertTemplate


@admin.register(CertTemplate)
class CertTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "default_lifetime_days", "max_lifetime_days", "is_system")
    readonly_fields = ("created_at", "updated_at")
