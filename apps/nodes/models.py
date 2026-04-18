import uuid

from django.db import models


class NodeConfig(models.Model):
    """Singleton: represents this node's identity, roles, and wizard state.

    Exactly one row exists with pk=1.
    """

    id = models.PositiveSmallIntegerField(primary_key=True, default=1)

    is_root = models.BooleanField(default=False)
    is_intermediate = models.BooleanField(default=False)
    is_issuing = models.BooleanField(default=False)

    wizard_step = models.PositiveSmallIntegerField(default=1)
    is_configured = models.BooleanField(default=False)

    fleet_uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    hostname = models.CharField(max_length=255, blank=True)

    root_lifetime_days = models.PositiveIntegerField(default=7300)
    intermediate_lifetime_days = models.PositiveIntegerField(default=3650)
    issuing_lifetime_days = models.PositiveIntegerField(default=1825)

    root_cn = models.CharField(max_length=255, default="ForgedCA Root CA")
    intermediate_cn = models.CharField(max_length=255, default="ForgedCA Intermediate CA")
    issuing_cn = models.CharField(max_length=255, default="ForgedCA Issuing CA")
    org = models.CharField(max_length=255, default="ForgedCA")

    root_cert_path = models.CharField(max_length=500, blank=True)
    root_key_path = models.CharField(max_length=500, blank=True)
    intermediate_cert_path = models.CharField(max_length=500, blank=True)
    intermediate_key_path = models.CharField(max_length=500, blank=True)
    issuing_cert_path = models.CharField(max_length=500, blank=True)
    issuing_key_path = models.CharField(max_length=500, blank=True)

    trust_download_requires_auth = models.BooleanField(default=False)
    default_acme_provisioner = models.CharField(max_length=100, default="forgedca-acme")

    created_at = models.DateTimeField(auto_now_add=True)
    configured_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Node configuration"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Singleton — never allow deletion.
        pass

    @classmethod
    def load(cls) -> "NodeConfig":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def roles_selected(self) -> list[str]:
        picked = []
        if self.is_root:
            picked.append("Root")
        if self.is_intermediate:
            picked.append("Intermediate")
        if self.is_issuing:
            picked.append("Issuing")
        return picked

    @property
    def has_any_role(self) -> bool:
        return self.is_root or self.is_intermediate or self.is_issuing

    @property
    def is_chain_local(self) -> bool:
        """True when this node has Root — the whole chain can be built
        locally without federation. False means a parent signer is needed
        over the network (deferred to slice 2)."""
        return self.is_root
