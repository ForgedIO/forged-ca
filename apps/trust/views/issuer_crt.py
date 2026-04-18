from django.views import View

from apps.nodes.models import NodeConfig
from apps.trust.helpers.download import auth_gate_or_404, serve_single_pem


class IssuerCrtView(View):
    def get(self, request):
        auth_gate_or_404(request)
        config = NodeConfig.load()
        return serve_single_pem(config.issuing_cert_path, "issuer_ca.crt")
