"""Generate the Root/Intermediate/Issuing certificate chain on this node.

Slice 1 scope: any role combination *including Root* is handled locally by
shelling out to `step certificate create`. Non-Root configurations are
deferred to slice 2 (federated CSR flow).
"""
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

log = logging.getLogger(__name__)


class KeygenError(RuntimeError):
    """Raised when a `step certificate create` invocation fails."""


@dataclass
class GeneratedArtifact:
    tier: str
    cert_path: Path
    key_path: Path


def _step_binary() -> str:
    step = shutil.which("step")
    if not step:
        raise KeygenError(
            "`step` CLI not found in PATH. Re-run install.sh or install the "
            "step CLI from https://smallstep.com/docs/step-cli/installation ."
        )
    return step


def _lifetime_flag(days: int) -> str:
    # step accepts Go duration syntax. Days × 24h keeps the math obvious and
    # lets step do its own validation.
    return f"{days * 24}h"


def _run_step(args: list[str]) -> None:
    log.info("step %s", " ".join(args))
    result = subprocess.run(
        [_step_binary(), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise KeygenError(
            f"step {' '.join(args)} failed (exit {result.returncode}):\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


def _paths() -> dict[str, Path]:
    base = Path(settings.STEP_CA_CONFIG_DIR)
    return {
        "root_cert": base / "certs" / "root_ca.crt",
        "root_key": base / "secrets" / "root_ca_key",
        "int_cert": base / "certs" / "intermediate_ca.crt",
        "int_key": base / "secrets" / "intermediate_ca_key",
        "iss_cert": base / "certs" / "issuer_ca.crt",
        "iss_key": base / "secrets" / "issuer_ca_key",
    }


def generate_chain(config) -> list[GeneratedArtifact]:
    """Generate keys and certs for whatever roles are set on `config`.

    Requires `config.is_root` — the chain is anchored locally. Configs
    without Root are the federation path and raise.
    """
    if not config.is_root:
        raise KeygenError(
            "Slice 1 only supports role combinations that include Root. "
            "Join-an-existing-Root flow is coming in slice 2."
        )

    paths = _paths()
    artifacts: list[GeneratedArtifact] = []

    # Root — self-signed
    _run_step([
        "certificate", "create",
        "--profile", "root-ca",
        "--no-password", "--insecure",
        "--not-after", _lifetime_flag(config.root_lifetime_days),
        "--force",
        config.root_cn,
        str(paths["root_cert"]),
        str(paths["root_key"]),
    ])
    _chmod_key(paths["root_key"])
    artifacts.append(GeneratedArtifact("root", paths["root_cert"], paths["root_key"]))
    config.root_cert_path = str(paths["root_cert"])
    config.root_key_path = str(paths["root_key"])

    # Intermediate — signed by local Root
    if config.is_intermediate:
        _run_step([
            "certificate", "create",
            "--profile", "intermediate-ca",
            "--ca", str(paths["root_cert"]),
            "--ca-key", str(paths["root_key"]),
            "--no-password", "--insecure",
            "--not-after", _lifetime_flag(config.intermediate_lifetime_days),
            "--force",
            config.intermediate_cn,
            str(paths["int_cert"]),
            str(paths["int_key"]),
        ])
        _chmod_key(paths["int_key"])
        artifacts.append(GeneratedArtifact("intermediate", paths["int_cert"], paths["int_key"]))
        config.intermediate_cert_path = str(paths["int_cert"])
        config.intermediate_key_path = str(paths["int_key"])

    # Issuing — signed by local Intermediate if present, else by Root
    if config.is_issuing:
        if config.is_intermediate:
            signer_cert = paths["int_cert"]
            signer_key = paths["int_key"]
        else:
            signer_cert = paths["root_cert"]
            signer_key = paths["root_key"]
        _run_step([
            "certificate", "create",
            "--profile", "intermediate-ca",
            "--ca", str(signer_cert),
            "--ca-key", str(signer_key),
            "--no-password", "--insecure",
            "--not-after", _lifetime_flag(config.issuing_lifetime_days),
            "--force",
            config.issuing_cn,
            str(paths["iss_cert"]),
            str(paths["iss_key"]),
        ])
        _chmod_key(paths["iss_key"])
        artifacts.append(GeneratedArtifact("issuing", paths["iss_cert"], paths["iss_key"]))
        config.issuing_cert_path = str(paths["iss_cert"])
        config.issuing_key_path = str(paths["iss_key"])

    return artifacts


def _chmod_key(path: Path) -> None:
    # Owner rw, group r (so step-ca daemon in the step-ca group can read),
    # others nothing.
    try:
        os.chmod(path, 0o640)
    except OSError as e:
        log.warning("Could not chmod %s: %s", path, e)


# ---------------------------------------------------------------------------
# Web UI leaf certificate
# ---------------------------------------------------------------------------

NGINX_BIN_CANDIDATES = ("/usr/sbin/nginx", "/usr/bin/nginx")
WEBUI_CERT_PATH = Path("/opt/forgedca/certs/forgedca.crt")
WEBUI_KEY_PATH = Path("/opt/forgedca/certs/forgedca.key")


def _webui_signer(config) -> tuple[Path, Path]:
    """Best CA to sign the Web UI leaf: Issuing > Intermediate > Root."""
    paths = _paths()
    if config.is_issuing:
        return paths["iss_cert"], paths["iss_key"]
    if config.is_intermediate:
        return paths["int_cert"], paths["int_key"]
    return paths["root_cert"], paths["root_key"]


def _webui_chain_paths(config, signer_cert: Path) -> list[Path]:
    """CA certs to concatenate below the leaf, in client-validation order.

    Never includes the Root when other CAs are present — the client already
    trusts the Root. Root is only included when it IS the signer (root-only
    config), so nginx has at least the signer in its served chain."""
    chain: list[Path] = [signer_cert]
    paths = _paths()
    if signer_cert == paths["iss_cert"] and config.intermediate_cert_path:
        chain.append(Path(config.intermediate_cert_path))
    return chain


def _parse_sans(text: str) -> list[str]:
    """One non-empty line per SAN. step-cli auto-classifies DNS vs IP from the value."""
    return [line.strip() for line in (text or "").splitlines() if line.strip() and not line.strip().startswith("#")]


def _reload_nginx() -> None:
    for bin_path in NGINX_BIN_CANDIDATES:
        if Path(bin_path).is_file():
            result = subprocess.run(
                ["sudo", "-n", bin_path, "-s", "reload"],
                capture_output=True, text=True, check=False,
            )
            if result.returncode != 0:
                log.warning("nginx reload exited %s: %s", result.returncode, result.stderr)
            return
    log.warning("nginx binary not found at any expected path; skipping reload")


def generate_webui_cert(config) -> GeneratedArtifact:
    """Issue a leaf cert for the admin UI signed by this node's own CA chain
    and swap it in at /opt/forgedca/certs/forgedca.{crt,key}, then reload
    nginx so the next page load is served with a CA-signed cert."""
    sans = _parse_sans(config.webui_sans)
    if not sans:
        raise KeygenError(
            "No Subject Alternative Names configured for the Web UI certificate. "
            "Add at least one DNS name or IP on the Lifetimes step."
        )

    signer_cert, signer_key = _webui_signer(config)

    # step writes leaf + key into scratch files we concatenate into the
    # final nginx cert next.
    tmp_cert = WEBUI_CERT_PATH.with_suffix(".leaf.crt")
    tmp_key = WEBUI_CERT_PATH.with_suffix(".leaf.key")

    common_name = sans[0]
    step_args = [
        "certificate", "create",
        "--profile", "leaf",
        "--ca", str(signer_cert),
        "--ca-key", str(signer_key),
        "--no-password", "--insecure",
        "--not-after", _lifetime_flag(config.webui_lifetime_days),
        "--force",
    ]
    for san in sans:
        step_args += ["--san", san]
    step_args += [common_name, str(tmp_cert), str(tmp_key)]
    _run_step(step_args)

    # Build the fullchain nginx will serve: leaf + signer (+ Intermediate when
    # signer is Issuing). Root is never in the wire chain — client has it.
    parts: list[bytes] = [tmp_cert.read_bytes().rstrip() + b"\n"]
    for ca_path in _webui_chain_paths(config, signer_cert):
        if ca_path.is_file():
            parts.append(ca_path.read_bytes().rstrip() + b"\n")

    WEBUI_CERT_PATH.parent.mkdir(parents=True, exist_ok=True)
    WEBUI_CERT_PATH.write_bytes(b"".join(parts))
    os.chmod(WEBUI_CERT_PATH, 0o644)
    # Atomically replace the key — write next to it then rename.
    tmp_key.replace(WEBUI_KEY_PATH)
    os.chmod(WEBUI_KEY_PATH, 0o600)
    # Leaf temp cert already consumed into the fullchain; drop it.
    tmp_cert.unlink(missing_ok=True)

    config.webui_cert_path = str(WEBUI_CERT_PATH)
    config.webui_key_path = str(WEBUI_KEY_PATH)

    _reload_nginx()
    return GeneratedArtifact("webui", WEBUI_CERT_PATH, WEBUI_KEY_PATH)
