from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.nodes.models import NodeConfig


@login_required
def home(request):
    config = NodeConfig.load()
    if not config.is_configured:
        return redirect("wizard:step_role")
    return render(request, "core/home.html", {"config": config})
