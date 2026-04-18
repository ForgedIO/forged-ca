from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views import View

from apps.nodes.models import NodeConfig
from apps.trust.helpers.download import read_all_pems


class TrustIndexView(LoginRequiredMixin, View):
    template_name = "trust/index.html"

    def get(self, request):
        config = NodeConfig.load()
        return render(request, self.template_name, {
            "config": config,
            "pems": read_all_pems(config),
        })
