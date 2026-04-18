from django import forms
from django.core.exceptions import ValidationError

from apps.nodes.helpers.network import parse_sans


class RoleSelectionForm(forms.Form):
    is_root = forms.BooleanField(required=False, label="Root CA")
    is_intermediate = forms.BooleanField(required=False, label="Intermediate CA")
    is_issuing = forms.BooleanField(required=False, label="Issuing CA")

    def clean(self):
        data = super().clean()
        if not any([data.get("is_root"), data.get("is_intermediate"), data.get("is_issuing")]):
            raise ValidationError("Pick at least one role.")
        return data


class LifetimesForm(forms.Form):
    hostname = forms.CharField(
        max_length=255,
        required=False,
        help_text="DNS name this node answers on. Leave blank to default to 'localhost'.",
    )
    org = forms.CharField(max_length=255, initial="ForgedCA")
    root_cn = forms.CharField(max_length=255, required=False)
    intermediate_cn = forms.CharField(max_length=255, required=False)
    issuing_cn = forms.CharField(max_length=255, required=False)
    root_lifetime_days = forms.IntegerField(
        min_value=365, max_value=36500, initial=7300,
        label="Root lifetime (days)",
        help_text="Recommended: 7300 days (20 years). Rotating the Root CA breaks trust everywhere it's installed, so private-PKI best practice is 20–25 years.",
    )
    intermediate_lifetime_days = forms.IntegerField(
        min_value=365, max_value=36500, initial=3650,
        label="Intermediate lifetime (days)",
        help_text="Recommended: 3650 days (10 years). Must be ≤ the Root's lifetime.",
    )
    issuing_lifetime_days = forms.IntegerField(
        min_value=30, max_value=36500, initial=1825,
        label="Issuing lifetime (days)",
        help_text="Recommended: 1825 days (5 years). Must be ≤ its parent's lifetime. This is the CA that signs day-to-day leaf certificates.",
    )

    webui_sans = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 5}),
        required=True,
        label="Web UI certificate — Subject Alternative Names",
        help_text=(
            "One DNS name or IP per line. nginx will serve the admin UI with a "
            "certificate signed by your new CA after the wizard finishes, so add "
            "every name and address you will use to reach this box. Pre-filled "
            "with the hostname and primary IP this machine already knows about."
        ),
    )
    webui_lifetime_days = forms.IntegerField(
        min_value=30, max_value=3650, initial=365,
        label="Web UI certificate lifetime (days)",
        help_text="Recommended: 365 days. When the ACME provisioner lands in slice 2 this cert will auto-renew, so a short lifetime is fine.",
    )

    def __init__(self, *args, node_config=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.node_config = node_config
        if node_config:
            if not node_config.is_root:
                self.fields.pop("root_cn")
                self.fields.pop("root_lifetime_days")
            if not node_config.is_intermediate:
                self.fields.pop("intermediate_cn")
                self.fields.pop("intermediate_lifetime_days")
            if not node_config.is_issuing:
                self.fields.pop("issuing_cn")
                self.fields.pop("issuing_lifetime_days")

    def clean_webui_sans(self):
        raw = self.cleaned_data.get("webui_sans", "")
        dns, ips = parse_sans(raw)
        if not dns and not ips:
            raise ValidationError("Add at least one DNS name or IP.")
        return "\n".join(dns + ips)

    def clean(self):
        data = super().clean()
        cfg = self.node_config
        if not cfg:
            return data
        root_days = data.get("root_lifetime_days")
        int_days = data.get("intermediate_lifetime_days")
        iss_days = data.get("issuing_lifetime_days")
        if cfg.is_intermediate and cfg.is_root and int_days and root_days and int_days > root_days:
            raise ValidationError("Intermediate lifetime must be ≤ Root lifetime.")
        parent_for_issuing = int_days if cfg.is_intermediate else root_days
        if cfg.is_issuing and iss_days and parent_for_issuing and iss_days > parent_for_issuing:
            raise ValidationError("Issuing lifetime must be ≤ its parent's lifetime.")
        webui_days = data.get("webui_lifetime_days")
        issuer_for_webui = iss_days or int_days or root_days
        if webui_days and issuer_for_webui and webui_days > issuer_for_webui:
            raise ValidationError("Web UI lifetime must be ≤ the CA signing it.")
        return data
