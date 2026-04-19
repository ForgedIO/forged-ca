"""Re-render /etc/step-ca/ca.json from current model state, then SIGHUP step-ca.

Needed because the first ca.json is written during the wizard's key-gen step,
before other apps (ACME provisioner, templates in later slices) have had a
chance to populate their config tables. Running this from update.sh keeps the
on-disk ca.json in sync with whatever Django models say on every deploy,
without requiring the admin to click Save on the ACME form.

Idempotent — if ca.json already matches current state, the SIGHUP is a no-op.
"""
from django.core.management.base import BaseCommand

from apps.ca import daemon, renderer
from apps.nodes.models import NodeConfig


class Command(BaseCommand):
    help = "Re-render /etc/step-ca/ca.json and reload step-ca."

    def handle(self, *args, **options):
        config = NodeConfig.load()
        if not config.is_issuing:
            self.stdout.write("Not an Issuing node — nothing to render.")
            return

        path = renderer.write(config)
        if path is None:
            self.stdout.write(self.style.WARNING(
                "renderer.write returned None — node role doesn't require ca.json."))
            return
        self.stdout.write(self.style.SUCCESS(f"ca.json rendered → {path}"))

        status = daemon.status()
        if not status.installed:
            self.stdout.write("step-ca.service not installed — skipping reload.")
            return
        if not status.active:
            self.stdout.write("step-ca not currently active — skipping reload "
                              "(start it from Settings to pick up the new config).")
            return
        ok, err = daemon.reload()
        if ok:
            self.stdout.write(self.style.SUCCESS("step-ca reloaded (SIGHUP)."))
        else:
            self.stdout.write(self.style.WARNING(f"reload failed: {err}"))
