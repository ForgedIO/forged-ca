from django.urls import path

from .views import AuthoritiesView, DaemonActionView, DaemonStatusView, SignWebuiView


app_name = "ca"


urlpatterns = [
    path("", AuthoritiesView.as_view(), name="authorities"),
    path("sign-webui/", SignWebuiView.as_view(), name="sign_webui"),
    path("step-ca/status.json", DaemonStatusView.as_view(), name="daemon_status"),
    path("step-ca/<str:action>/", DaemonActionView.as_view(), name="daemon_action"),
]
