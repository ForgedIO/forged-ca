from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("wizard/", include("apps.wizard.urls")),
    path("trust/", include("apps.trust.urls")),
    path("ca/", include("apps.ca.urls")),
    path("certificates/", include("apps.issuance.urls")),
    path("acme/", include("apps.acme.urls")),
    path("cert-templates/", include("apps.templates_app.urls")),
    path("audit/", include("apps.auditlog.urls")),
    path("", include("apps.core.urls")),
]
