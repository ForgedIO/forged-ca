import logging

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.views import View


log = logging.getLogger(__name__)

MIN_PASSWORD_LEN = 8
FORBIDDEN_PASSWORD = "Password!"


class ChangePasswordView(LoginRequiredMixin, View):
    template_name = "core/change_password.html"

    def get(self, request):
        return render(request, self.template_name, {"error": None})

    def post(self, request):
        new = request.POST.get("new_password", "")
        confirm = request.POST.get("confirm_password", "")
        error = self._validate(new, confirm)
        if error:
            return render(request, self.template_name, {"error": error})

        request.user.set_password(new)
        request.user.save()
        self._clear_force_flag(request.user)
        update_session_auth_hash(request, request.user)
        messages.success(request, "Password updated.")
        return redirect("core:home")

    @staticmethod
    def _validate(new: str, confirm: str) -> str | None:
        if len(new) < MIN_PASSWORD_LEN:
            return f"Password must be at least {MIN_PASSWORD_LEN} characters."
        if new != confirm:
            return "Passwords do not match."
        if new == FORBIDDEN_PASSWORD:
            return "Pick a password different from the default."
        return None

    @staticmethod
    def _clear_force_flag(user) -> None:
        try:
            user.profile.must_change_password = False
            user.profile.save(update_fields=["must_change_password"])
        except Exception as e:
            log.warning("ChangePasswordView: clearing must_change_password failed: %s", e)
