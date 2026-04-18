"""Guards shared by wizard step views: redirect out if already done, redirect
back to step 1 if no role has been picked yet."""
from django.shortcuts import redirect


def redirect_if_configured(config):
    if config.is_configured:
        return redirect("core:home")
    return None


def redirect_if_no_role(config):
    if not config.has_any_role:
        return redirect("wizard:step_role")
    return None
