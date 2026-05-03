"""Host/network detection helpers for SAN pre-population.

The wizard asks the admin which DNS names + IPs should be on the Web UI
certificate. We pre-populate that textarea with whatever this machine
already knows about itself — the admin edits it if they have additional
names (e.g. a DNS CNAME or a load-balancer vhost)."""
import ipaddress
import socket


def detect_primary_ip() -> str | None:
    """Return the local LAN IP that would be used to reach the internet —
    the typical "how clients see me" address. Does not send traffic; uses
    the kernel's routing table via a UDP socket connect to a fictitious
    external target. Returns None if the host has no default route."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("1.1.1.1", 80))
            ip = s.getsockname()[0]
            return ip if ip and ip != "0.0.0.0" else None
    except OSError:
        return None


def detect_hostname() -> str:
    try:
        return socket.gethostname() or "localhost"
    except OSError:
        return "localhost"


def _looks_like_fqdn(name: str) -> bool:
    """A DNS SAN is only useful if it has at least one dot. Single-label
    names (`RootCA`, `localhost`, `myserver`) are non-FQDN and trip NSS-
    based validators (Firefox/Chrome) which can reject the whole cert as
    malformed even when the FQDN you connect to is in the SAN list too."""
    name = (name or "").strip().rstrip(".")
    return bool(name) and "." in name


def default_webui_sans(extra_hostname: str = "") -> str:
    """One-SAN-per-line text suitable for a <textarea> initial value.

    Includes the caller-supplied hostname (typically `config.hostname` —
    the public FQDN admins type in their browser), the OS hostname *only
    when it's an FQDN*, and the primary LAN IP. Order-preserving and
    deduped case-insensitively.

    Single-label names (e.g. `localhost`, the OS short hostname) are
    deliberately excluded: NSS — Firefox's and Chromium's crypto library —
    rejects DNS SANs that aren't FQDNs, and a single bad SAN entry causes
    the browser to reject the whole cert with a generic "self-signed /
    missing intermediates" error. Admins who genuinely need a single-label
    name can add it manually in the Settings SAN editor; we don't seed
    one as a default and silently break the cert."""
    sans: list[str] = []
    seen: set[str] = set()

    def add(v: str):
        v = v.strip()
        if v and v.lower() not in seen:
            seen.add(v.lower())
            sans.append(v)

    if extra_hostname and _looks_like_fqdn(extra_hostname):
        add(extra_hostname)
    os_host = detect_hostname()
    if _looks_like_fqdn(os_host):
        add(os_host)
    ip = detect_primary_ip()
    if ip:
        add(ip)
    return "\n".join(sans)


def parse_sans(text: str) -> tuple[list[str], list[str]]:
    """Split a textarea into (dns_names, ip_addresses).

    Each non-empty line is classified by whether it parses as an IP address;
    everything else is treated as a DNS name. Returns the two lists in the
    order they appeared, with duplicates removed."""
    dns_names: list[str] = []
    ips: list[str] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        try:
            ipaddress.ip_address(line)
            ips.append(line)
        except ValueError:
            dns_names.append(line)
    return dns_names, ips
