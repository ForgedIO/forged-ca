from django.urls import path

from .views import SignWebuiView


app_name = "ca"


urlpatterns = [
    path("sign-webui/", SignWebuiView.as_view(), name="sign_webui"),
]
