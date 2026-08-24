from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views import View

from apps.nodes.models import NodeConfig


class SettingsEmailView(LoginRequiredMixin, View):
    """Email notification backend page (SMTP / Graph). Slice 8."""

    template_name = "core/settings/email.html"

    def get(self, request):
        config = NodeConfig.load()
        return render(request, self.template_name, {"config": config})
