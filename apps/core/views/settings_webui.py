from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views import View

from apps.nodes.models import NodeConfig


class SettingsWebuiCertView(LoginRequiredMixin, View):
    """Web UI certificate page.

    Shows the cert status and the SAN editor that drives ca:sign_webui. The
    sign action itself is a POST to ca:sign_webui, which redirects back here.
    """

    template_name = "core/settings/webui_cert.html"

    def get(self, request):
        config = NodeConfig.load()
        return render(request, self.template_name, {"config": config})
