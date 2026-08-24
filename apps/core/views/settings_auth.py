from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views import View

from apps.nodes.models import NodeConfig


class SettingsAuthView(LoginRequiredMixin, View):
    """Authentication backends page (LDAP / Entra ID / SAML / OIDC / Duo).

    All backends are "coming soon" — this page is the UI surface that each
    will fill in as its backend lands (Slice 4.5 LDAP + Entra, Slice 10 the
    rest).
    """

    template_name = "core/settings/auth.html"

    def get(self, request):
        config = NodeConfig.load()
        return render(request, self.template_name, {"config": config})
