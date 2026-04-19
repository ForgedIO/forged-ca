from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect
from django.views import View

from apps.ca import daemon
from apps.nodes.models import NodeConfig


ACTIONS = {
    "start":   (daemon.start,   "step-ca daemon started."),
    "stop":    (daemon.stop,    "step-ca daemon stopped."),
    "restart": (daemon.restart, "step-ca daemon restarted."),
    "reload":  (daemon.reload,  "step-ca daemon reloaded configuration."),
    "enable":  (daemon.enable,  "step-ca will now start on boot."),
}


class DaemonActionView(LoginRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, action):
        if action not in ACTIONS:
            return HttpResponseBadRequest(f"Unknown action: {action}")

        config = NodeConfig.load()
        if not config.is_issuing:
            messages.error(
                request,
                "step-ca only runs on nodes with an Issuing CA role.",
            )
            return redirect("core:settings")

        func, success_msg = ACTIONS[action]
        ok, stderr = func()
        if ok:
            # systemctl start/restart return before step-ca has fully reached
            # the active state. Give it a moment so the Settings page reflects
            # the real state on first render instead of the transient one.
            if action in {"start", "restart", "reload"}:
                daemon.wait_until_settled()
            messages.success(request, success_msg)
        else:
            messages.error(
                request,
                f"step-ca {action} failed: {stderr or 'see journalctl -u step-ca'}",
            )
        return redirect("core:settings")
