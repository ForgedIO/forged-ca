import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views import View

from apps.core.helpers.mfa import (
    clear_pending_secret,
    generate_recovery_codes,
    read_pending_secret,
    verify_totp,
)


log = logging.getLogger(__name__)


class MfaSetupConfirmView(LoginRequiredMixin, View):
    http_method_names = ["post"]
    template_name = "core/mfa_recovery_codes.html"

    def post(self, request):
        pending = read_pending_secret(request)
        if not pending:
            messages.error(request, "MFA setup expired. Try again.")
            return redirect("core:mfa_setup")

        code = request.POST.get("code", "").strip().replace(" ", "")
        if not verify_totp(pending, code):
            messages.error(request, "Invalid code. Scan the QR again and enter the current 6-digit code.")
            return redirect("core:mfa_setup")

        codes_plain, codes_hashed_json = generate_recovery_codes()
        self._persist_mfa(request.user.profile, pending, codes_hashed_json)
        clear_pending_secret(request)
        log.info("mfa_setup: enabled for user %s", request.user.username)
        return render(request, self.template_name, {"codes": codes_plain})

    @staticmethod
    def _persist_mfa(profile, pending_secret: str, codes_hashed_json: str) -> None:
        profile.mfa_secret = pending_secret
        profile.mfa_enabled = True
        profile.mfa_confirmed_at = timezone.now()
        profile.mfa_recovery_codes = codes_hashed_json
        profile.save(update_fields=["mfa_secret", "mfa_enabled", "mfa_confirmed_at", "mfa_recovery_codes"])
