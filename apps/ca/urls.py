from django.urls import path

from .views import AuthoritiesView, SignWebuiView


app_name = "ca"


urlpatterns = [
    path("", AuthoritiesView.as_view(), name="authorities"),
    path("sign-webui/", SignWebuiView.as_view(), name="sign_webui"),
]
