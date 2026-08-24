from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views import View

from apps.nodes.models import NodeConfig


class SettingsTrustDownloadView(LoginRequiredMixin, View):
    """Trust-download auth toggle page.

    The underlying flag is ``NodeConfig.trust_download_requires_auth``.
    The POST handler (and the UI that flips it) lands with the auth wiring —
    until then this page is a read-only indicator.
    """

    template_name = "core/settings/trust_download.html"

    def get(self, request):
        config = NodeConfig.load()
        return render(request, self.template_name, {"config": config})
