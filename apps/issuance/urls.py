from django.urls import path

from .views import IssuanceIndexView


app_name = "issuance"


urlpatterns = [
    path("", IssuanceIndexView.as_view(), name="index"),
]
