from django.shortcuts import redirect
from django.urls import resolve


EXEMPT_URL_NAMES = {
    "login",
    "logout",
}
EXEMPT_PATH_PREFIXES = (
    "/wizard/",
    "/admin/",
    "/static/",
    "/trust/",
    "/accounts/",
    # Pre-wizard hygiene paths — ForcePasswordChange / ForceMFASetup pin the
    # admin here; this middleware must not bounce them back to /wizard/ or
    # we get a loop.
    "/change-password/",
    "/mfa/",
    "/login/",
    "/logout/",
)


class WizardRedirectMiddleware:
    """If an authenticated user lands anywhere while the install wizard
    hasn't been completed, bounce them to the wizard. Exempts login/logout,
    the wizard itself, the Django admin, static assets, trust downloads,
    and allauth endpoints.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)

        path = request.path
        if any(path.startswith(p) for p in EXEMPT_PATH_PREFIXES):
            return self.get_response(request)

        try:
            match = resolve(path)
            if match.url_name in EXEMPT_URL_NAMES:
                return self.get_response(request)
        except Exception:
            pass

        from apps.nodes.models import NodeConfig
        config = NodeConfig.load()
        if not config.is_configured:
            return redirect("wizard:step_role")

        return self.get_response(request)
