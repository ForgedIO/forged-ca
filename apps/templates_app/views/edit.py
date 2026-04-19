from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.ca import daemon, renderer
from apps.nodes.models import NodeConfig

from ..forms import CertTemplateForm
from ..models import CertTemplate


def _reapply_ca_json():
    """Any template edit can change the lifetime/policy on a bound ACME
    provisioner — rewrite ca.json + SIGHUP step-ca so the change is live
    without needing the admin to hop to the ACME page."""
    config = NodeConfig.load()
    if not config.is_issuing:
        return
    try:
        renderer.write(config)
    except Exception:
        return
    if daemon.status().active:
        daemon.reload()


class TemplateCreateView(LoginRequiredMixin, View):
    template_name = "templates_app/form.html"

    def get(self, request):
        return render(request, self.template_name, {"form": CertTemplateForm(), "mode": "create"})

    def post(self, request):
        form = CertTemplateForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "mode": "create"})
        obj = form.save()
        _reapply_ca_json()
        messages.success(request, f"Template “{obj.name}” created.")
        return redirect("templates_app:index")


class TemplateEditView(LoginRequiredMixin, View):
    template_name = "templates_app/form.html"

    def get(self, request, pk):
        obj = get_object_or_404(CertTemplate, pk=pk)
        return render(request, self.template_name, {"form": CertTemplateForm(instance=obj), "mode": "edit", "obj": obj})

    def post(self, request, pk):
        obj = get_object_or_404(CertTemplate, pk=pk)
        form = CertTemplateForm(request.POST, instance=obj)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "mode": "edit", "obj": obj})
        form.save()
        _reapply_ca_json()
        messages.success(request, f"Template “{obj.name}” updated and step-ca reloaded.")
        return redirect("templates_app:index")
