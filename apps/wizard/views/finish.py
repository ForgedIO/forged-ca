from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.views import View

from apps.nodes.models import NodeConfig
from apps.trust.helpers.download import read_all_pems


class FinishView(LoginRequiredMixin, View):
    template_name = "wizard/finish.html"

    def get(self, request):
        config = NodeConfig.load()
        if not config.is_configured:
            return redirect("wizard:step_role")
        return render(request, self.template_name, {
            "config": config,
            "pems": read_all_pems(config),
        })
