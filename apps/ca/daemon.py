"""Thin wrapper over systemctl for the step-ca daemon.

install.sh drops a narrow sudoers entry at /etc/sudoers.d/forgedca-stepca so
this user can start/stop/reload/status step-ca without a blanket systemctl
grant. All calls go through `_systemctl` so we never shell-inject.

The ACME provisioner and everything built on it rely on the daemon being
up; when the renderer rewrites /etc/step-ca/ca.json we call `reload()` so
step-ca picks up the new provisioners without dropping in-flight ACME
validations.
"""
import shutil
import subprocess
import time
from dataclasses import dataclass


SERVICE = "step-ca"
_SYSTEMCTL = shutil.which("systemctl") or "/usr/bin/systemctl"


@dataclass
class DaemonStatus:
    installed: bool       # /etc/systemd/system/step-ca.service exists
    active: bool          # systemctl is-active returned "active"
    enabled: bool         # systemctl is-enabled returned "enabled"
    substate: str         # raw state word from systemctl (active / inactive / failed / …)
    message: str = ""     # short human-facing note for the UI


def _systemctl(*args: str, timeout: int = 10) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["sudo", "-n", _SYSTEMCTL, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def status() -> DaemonStatus:
    from pathlib import Path
    unit = Path("/etc/systemd/system/step-ca.service")
    if not unit.exists():
        return DaemonStatus(
            installed=False, active=False, enabled=False, substate="not-installed",
            message="step-ca.service is not installed on this host. Re-run install.sh.",
        )

    is_active = _systemctl("is-active", SERVICE)
    is_enabled = _systemctl("is-enabled", SERVICE)
    substate = (is_active.stdout or is_active.stderr or "unknown").strip()

    return DaemonStatus(
        installed=True,
        active=(substate == "active"),
        enabled=(is_enabled.stdout or "").strip() == "enabled",
        substate=substate,
    )


def start() -> tuple[bool, str]:
    r = _systemctl("start", SERVICE, timeout=30)
    return (r.returncode == 0, (r.stderr or r.stdout).strip())


def stop() -> tuple[bool, str]:
    r = _systemctl("stop", SERVICE, timeout=30)
    return (r.returncode == 0, (r.stderr or r.stdout).strip())


def restart() -> tuple[bool, str]:
    r = _systemctl("restart", SERVICE, timeout=30)
    return (r.returncode == 0, (r.stderr or r.stdout).strip())


def reload() -> tuple[bool, str]:
    """Graceful reload — step-ca reads ca.json on SIGHUP. Falls back to
    restart if the service isn't running (reload fails on inactive units)."""
    r = _systemctl("reload", SERVICE, timeout=30)
    if r.returncode == 0:
        return True, ""
    if status().active:
        return False, (r.stderr or r.stdout).strip()
    return restart()


def enable() -> tuple[bool, str]:
    r = _systemctl("enable", SERVICE, timeout=30)
    return (r.returncode == 0, (r.stderr or r.stdout).strip())


def wait_until_settled(timeout: float = 3.0, interval: float = 0.2) -> DaemonStatus:
    """Poll status() until the daemon reports a terminal state (active or
    failed) or we hit `timeout`. systemctl start returns before step-ca has
    fully transitioned, so redirecting straight to Settings often shows a
    stale 'inactive' even when the service came up cleanly."""
    deadline = time.monotonic() + timeout
    s = status()
    while time.monotonic() < deadline:
        s = status()
        if s.active or s.substate in {"failed", "not-found"}:
            return s
        time.sleep(interval)
    return s
