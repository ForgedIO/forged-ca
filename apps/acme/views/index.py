from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.views import View

from apps.ca import daemon, renderer
from apps.nodes.models import NodeConfig

from ..forms import ACMEProvisionerForm
from ..models import ACMEProvisioner


class AcmeIndexView(LoginRequiredMixin, View):
    template_name = "acme/index.html"

    def get(self, request):
        config = NodeConfig.load()
        provisioner = ACMEProvisioner.load()
        return render(request, self.template_name, self._context(request, config, provisioner))

    def post(self, request):
        config = NodeConfig.load()
        provisioner = ACMEProvisioner.load()
        form = ACMEProvisionerForm(request.POST, instance=provisioner)
        if not form.is_valid():
            return render(request, self.template_name,
                          self._context(request, config, provisioner, form=form))

        form.save()

        # Rewrite ca.json with the new provisioner config and nudge step-ca to
        # pick it up. reload() is a SIGHUP; step-ca re-reads ca.json live.
        apply_err = None
        if config.is_issuing:
            try:
                renderer.write(config)
            except Exception as e:
                apply_err = f"Could not write ca.json: {e}"
            else:
                ok, stderr = daemon.reload()
                if not ok:
                    apply_err = f"Saved, but step-ca reload failed: {stderr}"

        if apply_err:
            messages.warning(request, apply_err)
        else:
            messages.success(request, "ACME provisioner saved and step-ca reloaded.")
        return redirect("acme:index")

    def _context(self, request, config, provisioner, form=None):
        hostname = config.hostname or request.get_host().split(":")[0]
        step_ca_status = daemon.status() if config.is_issuing else None
        return {
            "config": config,
            "provisioner": provisioner,
            "form": form or ACMEProvisionerForm(instance=provisioner),
            "directory_url": provisioner.directory_url(hostname),
            "step_ca": step_ca_status,
        }
