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


def default_webui_sans(extra_hostname: str = "") -> str:
    """One-SAN-per-line text suitable for a <textarea> initial value.

    Always includes `localhost`. Adds the OS hostname, the primary LAN IP,
    and optionally a caller-supplied hostname (e.g. the hostname the admin
    typed earlier in the wizard) — dedup'd, order-preserving."""
    sans: list[str] = []
    seen: set[str] = set()

    def add(v: str):
        v = v.strip()
        if v and v.lower() not in seen:
            seen.add(v.lower())
            sans.append(v)

    if extra_hostname:
        add(extra_hostname)
    add(detect_hostname())
    add("localhost")
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
