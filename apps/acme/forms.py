from django import forms

from .models import ACMEProvisioner


class ACMEProvisionerForm(forms.ModelForm):
    """Admin-facing form for the single ACME provisioner.

    Lifetime is entered in days (admins think in days), stored in hours
    (step-ca speaks Go duration like `49d` → we normalise to hours because
    some step-ca versions don't accept `d` suffix on the stricter parser).
    """
    default_lifetime_days = forms.IntegerField(
        label="Default leaf lifetime (days)",
        min_value=1, max_value=825,
        help_text="Lifetime issued when the client doesn't request a specific "
                  "duration. 49 matches the 2029 public-web ceiling; shorter "
                  "drives faster rotation, longer is easier on devices that "
                  "can't reach the CA often.",
    )
    max_lifetime_days = forms.IntegerField(
        label="Maximum leaf lifetime (days)",
        min_value=1, max_value=825,
        help_text="Upper bound — an ACME client asking for more than this "
                  "gets silently capped at this value.",
    )

    class Meta:
        model = ACMEProvisioner
        fields = [
            "name", "enabled",
            "challenge_http01", "challenge_tls_alpn01", "challenge_dns01",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
        }
        labels = {
            "name": "Provisioner name",
            "enabled": "Enable ACME issuance on this node",
            "challenge_http01":     "HTTP-01 (baseline — port 80 fetch)",
            "challenge_tls_alpn01": "TLS-ALPN-01 (port 443 handshake)",
            "challenge_dns01":      "DNS-01 (requires a DNS provider plugin — v2)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get("instance") or self.instance
        if instance is not None:
            self.fields["default_lifetime_days"].initial = instance.default_leaf_lifetime_hours // 24
            self.fields["max_lifetime_days"].initial     = instance.max_leaf_lifetime_hours // 24

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name.replace("-", "").replace("_", "").isalnum():
            raise forms.ValidationError(
                "Only letters, digits, '-' and '_'. Appears in URL paths."
            )
        return name

    def clean(self):
        cleaned = super().clean()
        max_days = cleaned.get("max_lifetime_days") or 0
        default_days = cleaned.get("default_lifetime_days") or 0
        if max_days and default_days > max_days:
            raise forms.ValidationError(
                "Default lifetime cannot exceed the maximum.",
            )
        if not (cleaned.get("challenge_http01")
                or cleaned.get("challenge_tls_alpn01")
                or cleaned.get("challenge_dns01")):
            raise forms.ValidationError(
                "Enable at least one challenge type. HTTP-01 is the usual baseline.",
            )
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.default_leaf_lifetime_hours = self.cleaned_data["default_lifetime_days"] * 24
        obj.max_leaf_lifetime_hours     = self.cleaned_data["max_lifetime_days"]     * 24
        if commit:
            obj.save()
        return obj
