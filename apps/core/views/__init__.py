from .change_password import ChangePasswordView
from .home import HomeView
from .login import LoginView
from .logout import LogoutView
from .mfa_setup import MfaSetupView
from .mfa_setup_confirm import MfaSetupConfirmView
from .mfa_verify import MfaVerifyView
from .settings import SettingsView
from .settings_auth import SettingsAuthView
from .settings_daemon import SettingsDaemonView
from .settings_email import SettingsEmailView
from .settings_https_port import SettingsHttpsPortView
from .settings_syslog import SettingsSyslogView
from .settings_trust_download import SettingsTrustDownloadView
from .settings_users import SettingsUsersView
from .settings_webui import SettingsWebuiCertView


__all__ = [
    "ChangePasswordView",
    "HomeView",
    "LoginView",
    "LogoutView",
    "MfaSetupView",
    "MfaSetupConfirmView",
    "MfaVerifyView",
    "SettingsView",
    "SettingsAuthView",
    "SettingsDaemonView",
    "SettingsEmailView",
    "SettingsHttpsPortView",
    "SettingsSyslogView",
    "SettingsTrustDownloadView",
    "SettingsUsersView",
    "SettingsWebuiCertView",
]
