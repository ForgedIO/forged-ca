from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views import View

from apps.issuance.models import IssuedCertificate


class IssuanceIndexView(LoginRequiredMixin, View):
    template_name = "issuance/index.html"

    def get(self, request):
        # Get all issued certificates, ordered by most recent first
        certificates = IssuedCertificate.objects.select_related(
            'template', 'signed_by'
        ).all()
        
        return render(request, self.template_name, {
            'certificates': certificates,
        })
