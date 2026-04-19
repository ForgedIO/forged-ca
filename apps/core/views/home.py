from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.views import View

from apps.ca import daemon
from apps.nodes.models import NodeConfig
from apps.trust.helpers.download import read_all_pems


class HomeView(LoginRequiredMixin, View):
    template_name = "core/home.html"

    def get(self, request):
        config = NodeConfig.load()
        if not config.is_configured:
            return redirect("wizard:step_role")

        acme_provisioner = None
        step_ca = None
        if config.is_issuing:
            from apps.acme.models import ACMEProvisioner
            acme_provisioner = ACMEProvisioner.load()
            step_ca = daemon.status()

        return render(request, self.template_name, {
            "config": config,
            "pems": read_all_pems(config),
            "acme_provisioner": acme_provisioner,
            "step_ca": step_ca,
        })
