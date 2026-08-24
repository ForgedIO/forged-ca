from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views import View

from apps.nodes.models import NodeConfig


class SettingsSyslogView(LoginRequiredMixin, View):
    """Syslog forwarding config page. Slice 9."""

    template_name = "core/settings/syslog.html"

    def get(self, request):
        config = NodeConfig.load()
        return render(request, self.template_name, {"config": config})
