"""Writes to NodeConfig coming back from wizard form cleaned_data."""
from apps.nodes.models import NodeConfig


def apply_role_selection(config: NodeConfig, cleaned: dict) -> None:
    config.is_root = cleaned.get("is_root", False)
    config.is_intermediate = cleaned.get("is_intermediate", False)
    config.is_issuing = cleaned.get("is_issuing", False)


def apply_lifetimes(config: NodeConfig, cleaned: dict) -> None:
    config.hostname = cleaned.get("hostname", "") or ""
    config.org = cleaned.get("org", config.org)
    if config.is_root:
        config.root_cn = cleaned.get("root_cn") or config.root_cn
        config.root_lifetime_days = cleaned["root_lifetime_days"]
    if config.is_intermediate:
        config.intermediate_cn = cleaned.get("intermediate_cn") or config.intermediate_cn
        config.intermediate_lifetime_days = cleaned["intermediate_lifetime_days"]
    if config.is_issuing:
        config.issuing_cn = cleaned.get("issuing_cn") or config.issuing_cn
        config.issuing_lifetime_days = cleaned["issuing_lifetime_days"]
    if "webui_sans" in cleaned:
        config.webui_sans = cleaned["webui_sans"]
    if "webui_lifetime_days" in cleaned:
        config.webui_lifetime_days = cleaned["webui_lifetime_days"]
