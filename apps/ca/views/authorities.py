from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views import View

from apps.nodes.models import NodeConfig


class AuthoritiesView(LoginRequiredMixin, View):
    template_name = "ca/authorities.html"

    def get(self, request):
        config = NodeConfig.load()
        tiers = [
            {
                "name": "Root CA",
                "active": config.is_root,
                "cn": config.root_cn,
                "lifetime_days": config.root_lifetime_days,
                "cert_path": config.root_cert_path,
                "key_path": config.root_key_path,
                "signer": "Self-signed",
                "pathlen": "5 (step template)",
            },
            {
                "name": "Intermediate CA",
                "active": config.is_intermediate,
                "cn": config.intermediate_cn,
                "lifetime_days": config.intermediate_lifetime_days,
                "cert_path": config.intermediate_cert_path,
                "key_path": config.intermediate_key_path,
                "signer": "Root CA",
                "pathlen": "1",
            },
            {
                "name": "Issuing CA",
                "active": config.is_issuing,
                "cn": config.issuing_cn,
                "lifetime_days": config.issuing_lifetime_days,
                "cert_path": config.issuing_cert_path,
                "key_path": config.issuing_key_path,
                "signer": "Intermediate CA" if config.is_intermediate else "Root CA",
                "pathlen": "0 (signs leaves only)",
            },
        ]
        return render(request, self.template_name, {"config": config, "tiers": tiers})
