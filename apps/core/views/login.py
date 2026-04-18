import logging

from django.contrib.auth import authenticate, login
from django.shortcuts import redirect, render
from django.views import View

from apps.core.helpers.auth import resolve_username, safe_next_url
from apps.core.helpers.mfa_session import start_challenge


log = logging.getLogger(__name__)


class LoginView(View):
    template_name = "registration/login.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("core:home")
        return render(request, self.template_name, {"error": None})

    def post(self, request):
        if request.user.is_authenticated:
            return redirect("core:home")

        username = resolve_username(request.POST.get("username", "").strip())
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is None:
            return render(request, self.template_name, {"error": "Invalid username or password."})

        next_url = safe_next_url(request)
        if self._needs_mfa_challenge(user):
            start_challenge(request, user, next_url)
            return redirect("core:mfa_verify")

        login(request, user)
        return redirect(next_url)

    @staticmethod
    def _needs_mfa_challenge(user) -> bool:
        try:
            profile = user.profile
        except Exception as e:
            log.debug("LoginView: profile lookup failed: %s", e)
            return False
        return profile.mfa_enabled and profile.needs_mfa_at_login
