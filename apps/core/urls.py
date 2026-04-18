from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("change-password/", views.change_password, name="change_password"),
    path("mfa/setup/", views.mfa_setup, name="mfa_setup"),
    path("mfa/setup/confirm/", views.mfa_setup_confirm, name="mfa_setup_confirm"),
    path("mfa/verify/", views.mfa_verify, name="mfa_verify"),
]
