from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("wizard/", include("apps.wizard.urls")),
    path("trust/", include("apps.trust.urls")),
    path("ca/", include("apps.ca.urls")),
    path("", include("apps.core.urls")),
]
