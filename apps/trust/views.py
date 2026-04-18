"""Public trust-chain download endpoints.

Public by default; each node can flip `NodeConfig.trust_download_requires_auth`
to require a logged-in admin. CA certs are inherently public material, so the
default is "no auth" \u2014 an unauthenticated endpoint is what GPO / Intune /
Ansible / `step ca bootstrap` workflows actually need.
"""
from pathlib import Path

from django.http import Http404, HttpResponse

from apps.nodes.models import NodeConfig


def _auth_ok(request) -> bool:
    config = NodeConfig.load()
    if not config.trust_download_requires_auth:
        return True
    return request.user.is_authenticated


def _serve_pem(path_str: str, filename: str) -> HttpResponse:
    path = Path(path_str)
    if not path_str or not path.is_file():
        raise Http404("Certificate not available")
    resp = HttpResponse(path.read_bytes(), content_type="application/x-pem-file")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


def _gate(request):
    if not _auth_ok(request):
        raise Http404()


def root_crt(request):
    _gate(request)
    config = NodeConfig.load()
    return _serve_pem(config.root_cert_path, "root_ca.crt")


def intermediate_crt(request):
    _gate(request)
    config = NodeConfig.load()
    return _serve_pem(config.intermediate_cert_path, "intermediate_ca.crt")


def issuer_crt(request):
    _gate(request)
    config = NodeConfig.load()
    return _serve_pem(config.issuing_cert_path, "issuer_ca.crt")


def chain_pem(request):
    """Full chain \u2014 everything this node has, in top-down order."""
    _gate(request)
    config = NodeConfig.load()
    if not config.is_configured:
        raise Http404("CA not yet configured")

    parts: list[bytes] = []
    for path_str in (config.root_cert_path, config.intermediate_cert_path, config.issuing_cert_path):
        if path_str and Path(path_str).is_file():
            parts.append(Path(path_str).read_bytes().rstrip() + b"\n")
    if not parts:
        raise Http404("No certs available")

    resp = HttpResponse(b"".join(parts), content_type="application/x-pem-file")
    resp["Content-Disposition"] = 'attachment; filename="chain.pem"'
    return resp


def bundle_crt(request):
    """Root + Intermediate(s) only \u2014 the trust-anchor bundle for endpoints.
    Excludes the Issuing cert since endpoints don't trust that directly."""
    _gate(request)
    config = NodeConfig.load()
    if not config.is_configured:
        raise Http404("CA not yet configured")

    parts: list[bytes] = []
    for path_str in (config.root_cert_path, config.intermediate_cert_path):
        if path_str and Path(path_str).is_file():
            parts.append(Path(path_str).read_bytes().rstrip() + b"\n")
    if not parts:
        raise Http404("No certs available")

    resp = HttpResponse(b"".join(parts), content_type="application/x-pem-file")
    resp["Content-Disposition"] = 'attachment; filename="bundle.crt"'
    return resp
