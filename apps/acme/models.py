from django.db import models


class ACMEProvisioner(models.Model):
    """Singleton row holding this node's ACME provisioner settings.

    step-ca supports multiple ACME provisioners (one per bound cert template)
    and that's the shape later slices grow into. Slice 2B/3 keep it to one —
    a single "default" provisioner bound to the default template — so the
    single-server end-to-end ACME loop is operable before the provisioner-
    multiplexing UX lands.

    Lifetime policy lives on the bound CertTemplate (slice 3), not on this
    row. That way the admin changes lifetime in one place and it propagates
    to every provisioner sharing the template.
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

    template = models.ForeignKey(
        "templates_app.CertTemplate",
        on_delete=models.PROTECT,
        related_name="acme_provisioners",
        null=True, blank=True,
        help_text="Cert template whose lifetime + policy applies to leaves "
                  "issued via this provisioner. Defaults to the seeded "
                  "Web Server template if unset.",
    )

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
        from apps.templates_app.models import CertTemplate
        obj, _ = cls.objects.get_or_create(pk=cls.SINGLETON_ID)
        if obj.template_id is None:
            obj.template = CertTemplate.load_default()
            obj.save(update_fields=["template"])
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

    def effective_template(self):
        """Bound template or the seeded default — never None."""
        from apps.templates_app.models import CertTemplate
        return self.template or CertTemplate.load_default()

    def to_ca_json(self) -> dict:
        """Serialise for step-ca's authority.provisioners[] array."""
        t = self.effective_template()
        return {
            "type": "ACME",
            "name": self.name,
            "forceCN": False,
            "claims": {
                "defaultTLSCertDuration": f"{t.default_lifetime_hours}h",
                "minTLSCertDuration":     f"{t.min_lifetime_hours}h",
                "maxTLSCertDuration":     f"{t.max_lifetime_hours}h",
            },
            "challenges": self.active_challenges(),
        }

    def directory_url(self, hostname: str) -> str:
        return f"https://{hostname or 'localhost'}:9000/acme/{self.name}/directory"
