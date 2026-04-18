import logging

from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import redirect, render
from django.views import View

from apps.core.helpers.mfa import consume_recovery_code, verify_totp
from apps.core.helpers.mfa_session import (
    MAX_ATTEMPTS,
    clear_challenge,
    complete_challenge,
    pending_user,
    record_attempt,
)


log = logging.getLogger(__name__)


class MfaVerifyView(View):
    template_name = "core/mfa_verify.html"

    def get(self, request):
        user = pending_user(request)
        if user is None:
            return redirect("core:login")
        return render(request, self.template_name, {"error": None})

    def post(self, request):
        user = pending_user(request)
        if user is None:
            return redirect("core:login")

        attempts = record_attempt(request)
        if attempts > MAX_ATTEMPTS:
            messages.error(request, "Too many failed attempts. Sign in again.")
            clear_challenge(request)
            return redirect("core:login")

        code = request.POST.get("code", "").strip().replace(" ", "")
        if self._accept_code(user, code):
            next_url = complete_challenge(request)
            login(request, user)
            return redirect(next_url)
        return render(request, self.template_name, {"error": "Invalid code. Try again."})

    @staticmethod
    def _accept_code(user, code: str) -> bool:
        if verify_totp(user.profile.mfa_secret, code):
            return True
        if len(code) == 8 and consume_recovery_code(user.profile, code):
            log.info("mfa_verify: user %s used recovery code", user.username)
            return True
        return False
