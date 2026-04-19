from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View

from apps.ca import daemon
from apps.nodes.models import NodeConfig


class DaemonStatusView(LoginRequiredMixin, View):
    """JSON status endpoint polled by the Settings page so the admin sees the
    daemon transition live without a page reload. Authenticated only — we
    don't advertise service state to unauthenticated callers."""
    http_method_names = ["get"]

    def get(self, request):
        config = NodeConfig.load()
        if not config.is_issuing:
            return JsonResponse({"installed": False, "active": False, "reason": "not-issuing"})
        s = daemon.status()
        return JsonResponse({
            "installed": s.installed,
            "active": s.active,
            "enabled": s.enabled,
            "substate": s.substate,
            "message": s.message,
        })
