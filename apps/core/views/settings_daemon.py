from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views import View

from apps.ca import daemon
from apps.nodes.models import NodeConfig


class SettingsDaemonView(LoginRequiredMixin, View):
    """step-ca daemon control page.

    Carries the live daemon status, journal tail (when it will help), and the
    start/stop/restart/reload/enable controls. Polls ca:daemon_status for a
    live status readout (script lives in the template).
    """

    template_name = "core/settings/daemon.html"

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
