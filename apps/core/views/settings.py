from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views import View

from apps.ca import daemon
from apps.nodes.models import NodeConfig


class SettingsView(LoginRequiredMixin, View):
    template_name = "core/settings.html"

    def get(self, request):
        config = NodeConfig.load()
        step_ca = daemon.status() if config.is_issuing else None
        return render(request, self.template_name, {
            "config": config,
            "step_ca": step_ca,
        })
