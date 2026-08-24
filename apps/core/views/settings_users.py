from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views import View

from apps.nodes.models import NodeConfig


class SettingsUsersView(LoginRequiredMixin, View):
    """Admin user management page.

    Add / remove admin accounts, reset passwords, force-rotate MFA. The
    backend CRUD lands with the local-user-management slice; Django's own
    /admin/ is the interim fallback (linked from the template).
    """

    template_name = "core/settings/users.html"

    def get(self, request):
        config = NodeConfig.load()
        return render(request, self.template_name, {"config": config})
