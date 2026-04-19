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
        step_ca_log = None
        # Only pull the journal when it's likely to help — daemon stopped,
        # failed, or currently activating (the crash-loop case).
        if step_ca and step_ca.installed and (not step_ca.active or step_ca.substate == "activating"):
            step_ca_log = daemon.journal_tail(30)
        return render(request, self.template_name, {
            "config": config,
            "step_ca": step_ca,
            "step_ca_log": step_ca_log,
        })
