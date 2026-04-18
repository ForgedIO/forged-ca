from django.views import View

from apps.trust.helpers.download import (
    auth_gate_or_404,
    require_configured,
    serve_concatenated,
)


class BundleCrtView(View):
    """Root + Intermediate only — the trust-anchor bundle for endpoints.
    Excludes the Issuing cert since endpoints don't trust that directly."""

    def get(self, request):
        auth_gate_or_404(request)
        config = require_configured()
        return serve_concatenated(
            paths=[config.root_cert_path, config.intermediate_cert_path],
            filename="bundle.crt",
        )
