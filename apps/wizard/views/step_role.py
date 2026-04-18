from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.views import View

from apps.nodes.models import NodeConfig
from apps.wizard.forms import RoleSelectionForm
from apps.wizard.helpers.chain import apply_role_selection
from apps.wizard.helpers.guards import redirect_if_configured


SLICE_2_FEDERATION_MSG = (
    "This role combination requires federating to an existing Root. "
    "That flow is coming in slice 2 \u2014 for now, include Root to continue."
)


class StepRoleView(LoginRequiredMixin, View):
    template_name = "wizard/step_role.html"
    step = 1
    step_label = "Choose roles"

    def get(self, request):
        config = NodeConfig.load()
        done = redirect_if_configured(config)
        if done:
            return done
        form = RoleSelectionForm(initial={
            "is_root": config.is_root,
            "is_intermediate": config.is_intermediate,
            "is_issuing": config.is_issuing,
        })
        return render(request, self.template_name, self._context(form, config))

    def post(self, request):
        config = NodeConfig.load()
        done = redirect_if_configured(config)
        if done:
            return done

        form = RoleSelectionForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, self._context(form, config))

        apply_role_selection(config, form.cleaned_data)
        config.wizard_step = 2
        config.save()

        if not config.is_root:
            messages.info(request, SLICE_2_FEDERATION_MSG)
            return redirect("wizard:step_role")
        return redirect("wizard:step_lifetimes")

    def _context(self, form, config):
        return {
            "form": form,
            "config": config,
            "step": self.step,
            "step_label": self.step_label,
        }
