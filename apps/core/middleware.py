"""Pre-wizard middleware: forced password change + forced MFA enrollment.

Order in settings.MIDDLEWARE is important \u2014 these must come *before* the
wizard redirect so the admin is marched through password change \u2192 MFA
\u2192 wizard in that sequence."""
import logging

from django.shortcuts import redirect


EXEMPT_PREFIXES = (
    "/change-password/",
    "/mfa/",
    "/login/",
    "/logout/",
    "/admin/",
    "/static/",
    "/trust/",
    "/accounts/",
)


logger = logging.getLogger(__name__)


def _exempt(path: str) -> bool:
    return any(path.startswith(p) for p in EXEMPT_PREFIXES)


class ForcePasswordChangeMiddleware:
    """Redirect users with must_change_password=True to /change-password/."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not _exempt(request.path):
            try:
                if request.user.profile.must_change_password:
                    return redirect("core:change_password")
            except Exception as e:
                logger.debug("ForcePasswordChange: profile lookup failed: %s", e)
        return self.get_response(request)


class ForceMFASetupMiddleware:
    """Redirect users to /mfa/setup/ when MFA is enforced globally and this
    user hasn't enrolled yet. Skips IdPs that provide their own MFA (Entra,
    Duo-layered logins)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not _exempt(request.path):
            try:
                profile = request.user.profile
                if not profile.mfa_enabled and profile.needs_mfa_at_login:
                    from apps.core.models import MFAConfig
                    if MFAConfig.load().enforce_mfa:
                        return redirect("core:mfa_setup")
            except Exception as e:
                logger.debug("ForceMFASetup: profile lookup failed: %s", e)
        return self.get_response(request)
