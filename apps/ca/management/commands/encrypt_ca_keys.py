"""One-shot migration for boxes whose CA keys were generated before CA
passphrase encryption landed.

keygen.generate_chain() now always writes encrypted PKCS8 keys, but nodes
installed during early slice 2A wrote plaintext keys via --no-password
--insecure. update.sh calls this command so every pull-and-update cleanly
lifts those boxes onto the passphrase-encrypted model — re-wrapping the
existing key bytes in place (same CA identity, same cert chain, same
issued certs stay valid) rather than regenerating the chain.

Safe to run repeatedly: it's a no-op on keys that already load with a
password."""
from django.core.management.base import BaseCommand

from apps.ca import keygen


class Command(BaseCommand):
    help = "Encrypt any plaintext CA signing keys in place with the node's CA password."

    def handle(self, *args, **options):
        results = keygen.encrypt_existing_unencrypted_keys()
        if not results:
            self.stdout.write("No CA keys found on disk — nothing to encrypt.")
            return
        any_changed = False
        for tier, action in results:
            prefix = "changed" if action == "encrypted" else "ok"
            if action == "encrypted":
                any_changed = True
                self.stdout.write(self.style.SUCCESS(
                    f"  [{prefix}] {tier}: re-wrapped with CA password"
                ))
            else:
                self.stdout.write(f"  [{prefix}] {tier}: {action}")
        if any_changed:
            self.stdout.write(self.style.WARNING(
                "\nCA key material re-encrypted. Restart step-ca so it picks "
                "up the new keys with the configured --password-file."
            ))
