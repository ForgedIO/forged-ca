from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views import View

from ..models import CertTemplate


class TemplatesIndexView(LoginRequiredMixin, View):
    template_name = "templates_app/index.html"

    def get(self, request):
        # Ensure the seeded default exists so the list is never empty on a
        # fresh install — matches what the ACME load() call does at first use.
        CertTemplate.load_default()
        templates = CertTemplate.objects.all().order_by("-is_system", "name")
        return render(request, self.template_name, {"templates": templates})
