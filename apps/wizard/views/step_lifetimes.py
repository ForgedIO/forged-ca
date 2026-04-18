from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.views import View

from apps.nodes.helpers.network import default_webui_sans
from apps.nodes.models import NodeConfig
from apps.wizard.forms import LifetimesForm
from apps.wizard.helpers.chain import apply_lifetimes
from apps.wizard.helpers.guards import redirect_if_configured, redirect_if_no_role


class StepLifetimesView(LoginRequiredMixin, View):
    template_name = "wizard/step_lifetimes.html"
    step = 2
    step_label = "Lifetimes and names"

    def get(self, request):
        config = NodeConfig.load()
        done = redirect_if_configured(config) or redirect_if_no_role(config)
        if done:
            return done
        form = LifetimesForm(node_config=config, initial=self._initial(config))
        return render(request, self.template_name, self._context(form, config))

    def post(self, request):
        config = NodeConfig.load()
        done = redirect_if_configured(config) or redirect_if_no_role(config)
        if done:
            return done

        form = LifetimesForm(request.POST, node_config=config)
        if not form.is_valid():
            return render(request, self.template_name, self._context(form, config))

        apply_lifetimes(config, form.cleaned_data)
        config.wizard_step = 3
        config.save()
        return redirect("wizard:step_review")

    @staticmethod
    def _initial(config):
        return {
            "hostname": config.hostname,
            "org": config.org,
            "root_cn": config.root_cn,
            "intermediate_cn": config.intermediate_cn,
            "issuing_cn": config.issuing_cn,
            "root_lifetime_days": config.root_lifetime_days,
            "intermediate_lifetime_days": config.intermediate_lifetime_days,
            "issuing_lifetime_days": config.issuing_lifetime_days,
            "webui_sans": config.webui_sans or default_webui_sans(config.hostname),
            "webui_lifetime_days": config.webui_lifetime_days,
        }

    def _context(self, form, config):
        return {
            "form": form,
            "config": config,
            "step": self.step,
            "step_label": self.step_label,
        }
