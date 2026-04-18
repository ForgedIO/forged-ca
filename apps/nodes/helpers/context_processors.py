"""Template context processors.

`node_config` makes the NodeConfig singleton available to every template as
{{ node_config }}, so base.html can decide between the sidebar layout (for
configured / dashboard-and-beyond pages) and the centered layout (for login,
password-change, MFA setup, and wizard steps) without each view having to
pass `node_config` into context explicitly.
"""
from apps.nodes.models import NodeConfig


def node_config(request):
    try:
        return {"node_config": NodeConfig.load()}
    except Exception:
        # Database not ready yet (first install, pre-migrate) — fall back to
        # a placeholder so templates don't explode.
        return {"node_config": None}
