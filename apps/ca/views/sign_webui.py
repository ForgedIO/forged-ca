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
from apps.nodes.helpers.network import parse_sans
from apps.nodes.models import NodeConfig


class SignWebuiView(LoginRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request):
        config = NodeConfig.load()
        if not config.is_configured:
            messages.error(request, "Finish the install wizard first.")
            return redirect("wizard:step_role")
        if not config.is_issuing:
            messages.error(
                request,
                "Web UI signing is only offered on nodes that run an Issuing CA. "
                "On a Root- or Intermediate-only node, keep the install-time "
                "self-signed cert until you deploy an Issuing CA and federate "
                "it back to this node — leaf certificates should not be signed "
                "directly off a Root or Intermediate.",
            )
            return redirect("core:settings")

        # The Settings card POSTs the SAN list alongside the rotate button so
        # admins can fix a missing FQDN in one click instead of needing a
        # separate "edit SANs" page. parse_sans dedupes and classifies; an
        # empty result means the textarea was blank or whitespace-only.
        # Always carry config.hostname into the SANs — same invariant the
        # wizard enforces. Without it, an admin who clicks rotate without
        # editing the textarea ships a cert that doesn't cover the FQDN they
        # type in the browser.
        raw_sans = request.POST.get("webui_sans", "")
        if raw_sans.strip():
            if config.hostname and config.hostname.strip():
                raw_sans = config.hostname.strip() + "\n" + raw_sans
            dns, ips = parse_sans(raw_sans)
            if not dns and not ips:
                messages.error(request, "Add at least one DNS name or IP to the SAN list.")
                return redirect("core:settings")
            config.webui_sans = "\n".join(dns + ips)
            config.save(update_fields=["webui_sans"])

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
