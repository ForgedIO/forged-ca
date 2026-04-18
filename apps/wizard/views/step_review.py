from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views import View

from apps.ca import keygen, renderer
from apps.nodes.models import NodeConfig
from apps.wizard.helpers.guards import redirect_if_configured, redirect_if_no_role


class StepReviewView(LoginRequiredMixin, View):
    template_name = "wizard/step_review.html"
    step = 3
    step_label = "Review and generate"

    def get(self, request):
        config = NodeConfig.load()
        done = redirect_if_configured(config) or redirect_if_no_role(config)
        if done:
            return done
        return render(request, self.template_name, self._context(config))

    def post(self, request):
        config = NodeConfig.load()
        done = redirect_if_configured(config) or redirect_if_no_role(config)
        if done:
            return done

        try:
            keygen.generate_chain(config)
            renderer.write(config)
        except keygen.KeygenError as e:
            messages.error(request, f"Key generation failed: {e}")
            return redirect("wizard:step_review")

        config.is_configured = True
        config.configured_at = timezone.now()
        config.wizard_step = 4
        config.save()
        return redirect("wizard:finish")

    def _context(self, config):
        return {
            "config": config,
            "step": self.step,
            "step_label": self.step_label,
        }
