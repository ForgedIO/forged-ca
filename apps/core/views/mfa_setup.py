from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views import View

from apps.core.helpers.mfa import get_or_create_pending_secret, provisioning_qr_data_uri


TOTP_ISSUER = "ForgedCA"


class MfaSetupView(LoginRequiredMixin, View):
    template_name = "core/mfa_setup.html"

    def get(self, request):
        secret = get_or_create_pending_secret(request)
        account_name = request.user.email or request.user.username
        qr_data_uri = provisioning_qr_data_uri(secret=secret, name=account_name, issuer=TOTP_ISSUER)
        return render(request, self.template_name, {
            "qr_data_uri": qr_data_uri,
            "secret": secret,
            "already_enabled": request.user.profile.mfa_enabled,
        })
