from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.ca import daemon, renderer
from apps.nodes.models import NodeConfig

from ..forms import CertTemplateForm
from ..models import CertTemplate, USE_CASE_PRESETS


def _form_ctx(form, mode, obj=None):
    """Shared context for both create + edit form renders. Includes the
    use-case presets so form.html can embed them as JSON for the autofill JS."""
    ctx = {"form": form, "mode": mode, "use_case_presets": USE_CASE_PRESETS}
    if obj is not None:
        ctx["obj"] = obj
    return ctx


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
        return render(request, self.template_name, _form_ctx(CertTemplateForm(), "create"))

    def post(self, request):
        form = CertTemplateForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, _form_ctx(form, "create"))
        obj = form.save()
        _reapply_ca_json()
        messages.success(request, f"Template “{obj.name}” created.")
        return redirect("templates_app:index")


class TemplateEditView(LoginRequiredMixin, View):
    template_name = "templates_app/form.html"

    def get(self, request, pk):
        obj = get_object_or_404(CertTemplate, pk=pk)
        return render(request, self.template_name, _form_ctx(CertTemplateForm(instance=obj), "edit", obj))

    def post(self, request, pk):
        obj = get_object_or_404(CertTemplate, pk=pk)
        form = CertTemplateForm(request.POST, instance=obj)
        if not form.is_valid():
            return render(request, self.template_name, _form_ctx(form, "edit", obj))
        form.save()
        _reapply_ca_json()
        messages.success(request, f"Template “{obj.name}” updated and step-ca reloaded.")
        return redirect("templates_app:index")
