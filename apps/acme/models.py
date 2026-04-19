from django.db import models


class ACMEProvisioner(models.Model):
    """Singleton row holding this node's ACME provisioner settings.

    step-ca supports multiple ACME provisioners (one per bound cert template)
    and that's the shape slice 3 grows into. Slice 2B keeps it to one — a
    single "default" provisioner with the admin-tunable lifetime and
    challenge set — so the single-server end-to-end ACME loop is operable
    before the template-CRUD machinery lands.
    """
    SINGLETON_ID = 1

    name = models.CharField(
        max_length=63,
        default="forgedca-acme",
        help_text="Provisioner name — appears in the ACME directory URL "
                  "(https://<host>:9000/acme/<name>/directory). Changing this "
                  "breaks existing bootstrapped clients until they re-bootstrap.",
    )
    enabled = models.BooleanField(
        default=True,
        help_text="If disabled, step-ca will reject every ACME request. "
                  "Useful for maintenance windows or when the admin wants to "
                  "lock down issuance temporarily.",
    )

    # Defaults match CA/Browser Forum's 2029 public-cert ceiling (47 days). We
    # round up to 49 to give clients a margin on the renewal cron; ACME
    # clients typically renew at ⅓ remaining lifetime, so 49d → first renewal
    # attempt around day 33. Admin can tighten for dev, loosen for appliances.
    default_leaf_lifetime_hours = models.PositiveIntegerField(
        default=49 * 24,
        help_text="Lifetime issued when the client doesn't request a specific "
                  "duration. 49 days matches the 2029 public-web ceiling.",
    )
    min_leaf_lifetime_hours = models.PositiveIntegerField(default=1)
    max_leaf_lifetime_hours = models.PositiveIntegerField(default=365 * 24)

    # HTTP-01 is the baseline — every ACME client supports it, no plugin.
    # tls-alpn-01 is a nice-to-have for clients that can't open port 80
    # (e.g. TLS-passthrough LBs). dns-01 is deferred to a later slice because
    # it needs a provider plugin (route53 / cloudflare / rfc2136 / …).
    challenge_http01 = models.BooleanField(
        default=True,
        help_text="HTTP-01: CA fetches /.well-known/acme-challenge/<token> "
                  "on port 80. Baseline — keep enabled.",
    )
    challenge_tls_alpn01 = models.BooleanField(
        default=False,
        help_text="TLS-ALPN-01: CA opens a TLS connection with the "
                  "acme-tls/1 protocol. Useful when the client owns port 443 "
                  "but not port 80.",
    )
    challenge_dns01 = models.BooleanField(
        default=False,
        help_text="DNS-01: CA checks a TXT record. Requires a DNS-provider "
                  "plugin (AWS Route 53, Cloudflare, RFC 2136, …). The plugin "
                  "UI ships in a later slice; leave off for now.",
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "ACME provisioner"

    def __str__(self):
        return f"ACME: {self.name} ({'enabled' if self.enabled else 'disabled'})"

    @classmethod
    def load(cls) -> "ACMEProvisioner":
        obj, _ = cls.objects.get_or_create(pk=cls.SINGLETON_ID)
        return obj

    def save(self, *args, **kwargs):
        self.pk = self.SINGLETON_ID
        super().save(*args, **kwargs)

    def active_challenges(self) -> list[str]:
        chals: list[str] = []
        if self.challenge_http01:     chals.append("http-01")
        if self.challenge_tls_alpn01: chals.append("tls-alpn-01")
        if self.challenge_dns01:      chals.append("dns-01")
        # Never render an empty challenge list — step-ca rejects the provisioner.
        return chals or ["http-01"]

    def to_ca_json(self) -> dict:
        """Serialise for step-ca's authority.provisioners[] array."""
        return {
            "type": "ACME",
            "name": self.name,
            "forceCN": False,
            "claims": {
                "defaultTLSCertDuration": f"{self.default_leaf_lifetime_hours}h",
                "minTLSCertDuration":     f"{self.min_leaf_lifetime_hours}h",
                "maxTLSCertDuration":     f"{self.max_leaf_lifetime_hours}h",
            },
            "challenges": self.active_challenges(),
        }

    def directory_url(self, hostname: str) -> str:
        return f"https://{hostname or 'localhost'}:9000/acme/{self.name}/directory"
