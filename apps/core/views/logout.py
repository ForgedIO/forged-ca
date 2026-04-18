from django.contrib.auth import logout
from django.shortcuts import redirect
from django.views import View


class LogoutView(View):
    """Accepts GET or POST so the nav button and direct URL both work."""

    def get(self, request):
        return self.post(request)

    def post(self, request):
        logout(request)
        return redirect("core:login")
