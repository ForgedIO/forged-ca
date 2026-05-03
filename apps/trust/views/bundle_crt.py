from django.views import View

from apps.trust.helpers.download import (
    auth_gate_or_404,
    require_configured,
    serve_concatenated,
)


class BundleCrtView(View):
    """Root + Intermediate + Issuing — the full endpoint trust bundle.

    We ship all three CAs (not just the Root) because real-world browser
    chain-builders don't reliably use an Issuing CA cert presented on the
    wire to bridge a leaf to a locally-trusted Intermediate. Same chain
    validates fine for some leaves and fails for others, with no
    measurable cert-level cause we can find. Anchoring all three on the
    endpoint is a side-step that doesn't weaken the trust model — the
    Issuing CA is still subordinate to the Intermediate and Root, and
    cryptographic verification of any signed leaf still walks the same
    chain — it just removes the dependency on the browser's chain-build
    heuristic correctly stitching the Issuing in from the wire."""

    def get(self, request):
        auth_gate_or_404(request)
        config = require_configured()
        return serve_concatenated(
            paths=[
                config.root_cert_path,
                config.intermediate_cert_path,
                config.issuing_cert_path,
            ],
            filename="bundle.crt",
        )
