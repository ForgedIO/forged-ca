from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.ca import keygen, renderer
from apps.nodes.models import NodeConfig

from .forms import LifetimesForm, RoleSelectionForm


def _already_done(config: NodeConfig):
    if config.is_configured:
        return redirect("core:home")
    return None


@login_required
def step_role(request):
    config = NodeConfig.load()
    done = _already_done(config)
    if done:
        return done

    if request.method == "POST":
        form = RoleSelectionForm(request.POST)
        if form.is_valid():
            config.is_root = form.cleaned_data["is_root"]
            config.is_intermediate = form.cleaned_data["is_intermediate"]
            config.is_issuing = form.cleaned_data["is_issuing"]
            config.wizard_step = 2
            config.save()

            if not config.is_root:
                messages.info(
                    request,
                    "This role combination requires federating to an existing Root. "
                    "That flow is coming in slice 2 \u2014 for now, include Root to continue.",
                )
                return redirect("wizard:step_role")
            return redirect("wizard:step_lifetimes")
    else:
        form = RoleSelectionForm(initial={
            "is_root": config.is_root,
            "is_intermediate": config.is_intermediate,
            "is_issuing": config.is_issuing,
        })

    return render(request, "wizard/step_role.html", {
        "form": form,
        "config": config,
        "step": 1,
        "step_label": "Choose roles",
    })


@login_required
def step_lifetimes(request):
    config = NodeConfig.load()
    done = _already_done(config)
    if done:
        return done
    if not config.has_any_role:
        return redirect("wizard:step_role")

    if request.method == "POST":
        form = LifetimesForm(request.POST, node_config=config)
        if form.is_valid():
            cd = form.cleaned_data
            config.hostname = cd.get("hostname", "") or ""
            config.org = cd.get("org", config.org)
            if config.is_root:
                config.root_cn = cd.get("root_cn") or config.root_cn
                config.root_lifetime_days = cd["root_lifetime_days"]
            if config.is_intermediate:
                config.intermediate_cn = cd.get("intermediate_cn") or config.intermediate_cn
                config.intermediate_lifetime_days = cd["intermediate_lifetime_days"]
            if config.is_issuing:
                config.issuing_cn = cd.get("issuing_cn") or config.issuing_cn
                config.issuing_lifetime_days = cd["issuing_lifetime_days"]
            config.wizard_step = 3
            config.save()
            return redirect("wizard:step_review")
    else:
        form = LifetimesForm(node_config=config, initial={
            "hostname": config.hostname,
            "org": config.org,
            "root_cn": config.root_cn,
            "intermediate_cn": config.intermediate_cn,
            "issuing_cn": config.issuing_cn,
            "root_lifetime_days": config.root_lifetime_days,
            "intermediate_lifetime_days": config.intermediate_lifetime_days,
            "issuing_lifetime_days": config.issuing_lifetime_days,
        })

    return render(request, "wizard/step_lifetimes.html", {
        "form": form,
        "config": config,
        "step": 2,
        "step_label": "Lifetimes and names",
    })


@login_required
def step_review(request):
    config = NodeConfig.load()
    done = _already_done(config)
    if done:
        return done
    if not config.has_any_role:
        return redirect("wizard:step_role")

    if request.method == "POST":
        try:
            keygen.generate_chain(config)
            renderer.write(config)
        except keygen.KeygenError as e:
            messages.error(request, f"Key generation failed: {e}")
            return redirect("wizard:step_review")

        config.is_configured = True
        config.configured_at = timezone.now()
        config.wizard_step = 4
        config.save()
        return redirect("wizard:finish")

    return render(request, "wizard/step_review.html", {
        "config": config,
        "step": 3,
        "step_label": "Review and generate",
    })


@login_required
def finish(request):
    config = NodeConfig.load()
    if not config.is_configured:
        return redirect("wizard:step_role")
    return render(request, "wizard/finish.html", {"config": config})
