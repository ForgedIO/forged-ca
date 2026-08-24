from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views import View

from apps.nodes.models import NodeConfig


class SettingsHttpsPortView(LoginRequiredMixin, View):
    """HTTPS port (8443 → 443) live-reconfig page.

    Currently read-only: the value is hardcoded until the live-reconfig
    backend lands (graceful nginx reload on port swap).
    """

    template_name = "core/settings/https_port.html"

    def get(self, request):
        config = NodeConfig.load()
        return render(request, self.template_name, {"config": config})
