from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views import View


class IssuanceIndexView(LoginRequiredMixin, View):
    template_name = "issuance/index.html"

    def get(self, request):
        return render(request, self.template_name)
