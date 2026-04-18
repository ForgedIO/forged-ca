from django.urls import path

from .views import AcmeIndexView


app_name = "acme"


urlpatterns = [
    path("", AcmeIndexView.as_view(), name="index"),
]
