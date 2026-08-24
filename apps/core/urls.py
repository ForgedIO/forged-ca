from django.urls import path

from .views import (
    ChangePasswordView,
    HomeView,
    LoginView,
    LogoutView,
    MfaSetupView,
    MfaSetupConfirmView,
    MfaVerifyView,
    SettingsView,
    SettingsAuthView,
    SettingsDaemonView,
    SettingsEmailView,
    SettingsHttpsPortView,
    SettingsSyslogView,
    SettingsTrustDownloadView,
    SettingsUsersView,
    SettingsWebuiCertView,
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

    # Settings — overview hub + per-setting sub-pages
    path("settings/", SettingsView.as_view(), name="settings"),
    path("settings/daemon/", SettingsDaemonView.as_view(), name="settings_daemon"),
    path("settings/webui-cert/", SettingsWebuiCertView.as_view(), name="settings_webui_cert"),
    path("settings/https-port/", SettingsHttpsPortView.as_view(), name="settings_https_port"),
    path("settings/trust-download/", SettingsTrustDownloadView.as_view(), name="settings_trust_download"),
    path("settings/auth/", SettingsAuthView.as_view(), name="settings_auth"),
    path("settings/users/", SettingsUsersView.as_view(), name="settings_users"),
    path("settings/email/", SettingsEmailView.as_view(), name="settings_email"),
    path("settings/syslog/", SettingsSyslogView.as_view(), name="settings_syslog"),
]
