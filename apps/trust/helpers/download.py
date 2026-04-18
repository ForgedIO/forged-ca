"""Shared helpers for the /trust/*.crt and /trust/*.pem endpoints.

Trust downloads are public by default (CA certs are public material and
GPO/Intune/Ansible pull them unattended). A per-node toggle flips them to
404 unless the request is authenticated."""
from pathlib import Path

from django.http import Http404, HttpResponse

from apps.nodes.models import NodeConfig


PEM_CONTENT_TYPE = "application/x-pem-file"


def auth_gate_or_404(request) -> None:
    config = NodeConfig.load()
    if not config.trust_download_requires_auth:
        return
    if not request.user.is_authenticated:
        raise Http404()


def serve_single_pem(path_str: str, filename: str) -> HttpResponse:
    path = Path(path_str) if path_str else None
    if not path or not path.is_file():
        raise Http404("Certificate not available")
    resp = HttpResponse(path.read_bytes(), content_type=PEM_CONTENT_TYPE)
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


def serve_concatenated(paths: list[str], filename: str) -> HttpResponse:
    parts: list[bytes] = []
    for path_str in paths:
        if path_str and Path(path_str).is_file():
            parts.append(Path(path_str).read_bytes().rstrip() + b"\n")
    if not parts:
        raise Http404("No certs available")
    resp = HttpResponse(b"".join(parts), content_type=PEM_CONTENT_TYPE)
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


def require_configured() -> NodeConfig:
    config = NodeConfig.load()
    if not config.is_configured:
        raise Http404("CA not yet configured")
    return config
