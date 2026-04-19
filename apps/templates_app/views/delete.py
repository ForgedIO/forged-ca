from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from ..models import CertTemplate


class TemplateDeleteView(LoginRequiredMixin, View):
    template_name = "templates_app/delete.html"

    def get(self, request, pk):
        obj = get_object_or_404(CertTemplate, pk=pk)
        return render(request, self.template_name, self._context(obj))

    def post(self, request, pk):
        obj = get_object_or_404(CertTemplate, pk=pk)
        if obj.is_system:
            messages.error(request, "System templates can't be deleted.")
            return redirect("templates_app:index")
        if obj.acme_provisioners.exists():
            messages.error(
                request,
                f"Template “{obj.name}” is bound to an ACME provisioner. "
                "Rebind the provisioner first, then delete.",
            )
            return redirect("templates_app:index")
        name = obj.name
        obj.delete()
        messages.success(request, f"Template “{name}” deleted.")
        return redirect("templates_app:index")

    def _context(self, obj):
        return {
            "obj": obj,
            "in_use_by": list(obj.acme_provisioners.values_list("name", flat=True)),
        }
