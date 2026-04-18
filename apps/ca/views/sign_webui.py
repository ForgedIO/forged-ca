"""Swap the nginx-served admin UI cert to one signed by this node's own CA.

Runs as a post-wizard, admin-triggered action — NOT during the wizard itself.
Swapping the Web UI cert before the admin has installed the Root on their
device breaks their browser session (Firefox especially refuses to re-open
a page when the server cert suddenly becomes signed by an unknown CA), and
they lose the only way back into the admin UI to download and install that
Root. Issuing this cert via an explicit dashboard action keeps the admin in
control of when the cut-over happens."""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views import View

from apps.ca import keygen
from apps.nodes.models import NodeConfig


class SignWebuiView(LoginRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request):
        config = NodeConfig.load()
        if not config.is_configured:
            messages.error(request, "Finish the install wizard first.")
            return redirect("wizard:step_role")
        if not config.has_any_role or not config.is_root:
            messages.error(
                request,
                "This node does not have a local CA chain capable of signing the Web UI cert.",
            )
            return redirect("core:settings")

        try:
            keygen.generate_webui_cert(config)
        except keygen.KeygenError as e:
            messages.error(request, f"Web UI certificate issuance failed: {e}")
            return redirect("core:settings")

        config.save(update_fields=["webui_cert_path", "webui_key_path"])
        messages.success(
            request,
            "Web UI certificate swapped. Refresh this page — if you've installed "
            "the Root on this device, the browser will show a trusted lock.",
        )
        return redirect("core:settings")
