from django.urls import path

from .views import AuditlogIndexView


app_name = "auditlog"


urlpatterns = [
    path("", AuditlogIndexView.as_view(), name="index"),
]
