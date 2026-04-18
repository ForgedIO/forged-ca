from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.views import View

from apps.nodes.models import NodeConfig


class HomeView(LoginRequiredMixin, View):
    template_name = "core/home.html"

    def get(self, request):
        config = NodeConfig.load()
        if not config.is_configured:
            return redirect("wizard:step_role")
        return render(request, self.template_name, {"config": config})
