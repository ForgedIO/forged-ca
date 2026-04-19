from django.urls import path

from .views import AcmeIndexView, AcmeOnboardingView


app_name = "acme"


urlpatterns = [
    path("", AcmeIndexView.as_view(), name="index"),
    path("onboarding/", AcmeOnboardingView.as_view(), name="onboarding"),
]
