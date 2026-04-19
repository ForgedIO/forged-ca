from django import forms

from apps.templates_app.models import CertTemplate

from .models import ACMEProvisioner


class ACMEProvisionerForm(forms.ModelForm):
    """Admin-facing form for the single ACME provisioner.

    Lifetime no longer lives here — it's on the bound CertTemplate. The form
    surfaces the template picker + the template's current values (read-only)
    so the admin sees what's live without leaving the page.
    """

    class Meta:
        model = ACMEProvisioner
        fields = [
            "name", "enabled", "template",
            "challenge_http01", "challenge_tls_alpn01", "challenge_dns01",
        ]
        widgets = {
            "name":     forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "template": forms.Select(attrs={"class": "select select-bordered w-full"}),
        }
        labels = {
            "name":     "Provisioner name",
            "enabled":  "Enable ACME issuance on this node",
            "template": "Cert template",
            "challenge_http01":     "HTTP-01 (baseline — port 80 fetch)",
            "challenge_tls_alpn01": "TLS-ALPN-01 (port 443 handshake)",
            "challenge_dns01":      "DNS-01 (requires a DNS provider plugin — v2)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["template"].queryset = CertTemplate.objects.all().order_by("-is_system", "name")
        self.fields["template"].empty_label = None  # never None — default is always seeded

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name.replace("-", "").replace("_", "").isalnum():
            raise forms.ValidationError(
                "Only letters, digits, '-' and '_'. Appears in URL paths."
            )
        return name

    def clean(self):
        cleaned = super().clean()
        if not (cleaned.get("challenge_http01")
                or cleaned.get("challenge_tls_alpn01")
                or cleaned.get("challenge_dns01")):
            raise forms.ValidationError(
                "Enable at least one challenge type. HTTP-01 is the usual baseline.",
            )
        return cleaned
