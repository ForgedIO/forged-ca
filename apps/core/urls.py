from django.urls import path

from .views import (
    ChangePasswordView,
    HomeView,
    LoginView,
    LogoutView,
    MfaSetupView,
    MfaSetupConfirmView,
    MfaVerifyView,
)


app_name = "core"


urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("change-password/", ChangePasswordView.as_view(), name="change_password"),
    path("mfa/setup/", MfaSetupView.as_view(), name="mfa_setup"),
    path("mfa/setup/confirm/", MfaSetupConfirmView.as_view(), name="mfa_setup_confirm"),
    path("mfa/verify/", MfaVerifyView.as_view(), name="mfa_verify"),
]
