from django.views import View

from apps.trust.helpers.download import (
    auth_gate_or_404,
    require_configured,
    serve_concatenated,
)


class ChainPemView(View):
    """Full chain — every cert this node has, top-down (Root → Intermediate → Issuing)."""

    def get(self, request):
        auth_gate_or_404(request)
        config = require_configured()
        return serve_concatenated(
            paths=[config.root_cert_path, config.intermediate_cert_path, config.issuing_cert_path],
            filename="chain.pem",
        )
