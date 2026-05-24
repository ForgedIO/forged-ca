import re

from django import forms
from django.utils.text import slugify

from .models import CertTemplate, EKU_CHOICES, KU_CHOICES


# Dotted-OID regex for the "advanced custom OIDs" escape hatch. Permissive
# on length but strict on shape — we don't want admins typing OpenSSL short
# names into a field that step-ca will pass through raw.
_OID_RE = re.compile(r"^\d+(\.\d+)+$")


class CertTemplateForm(forms.ModelForm):
    # MultipleChoiceField overrides the auto-generated JSONField widget so
    # admins see friendly checkboxes instead of a JSON textarea. The
    # checkbox class is set here so iterating `{% for c in form.field %}`
    # in the template picks up DaisyUI styling automatically.
    extended_key_usages = forms.MultipleChoiceField(
        choices=EKU_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "checkbox checkbox-primary checkbox-sm"}),
        required=False,
        help_text="What this certificate is allowed to be used for. Pick all that apply.",
    )
    key_usages = forms.MultipleChoiceField(
        choices=KU_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "checkbox checkbox-primary checkbox-sm"}),
        required=False,
        help_text="Low-level Key Usage bits. Defaults match common EKU pairings — usually no need to override.",
    )
    # Comma-separated text input that converts to/from the JSONField list.
    custom_eku_oids = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "input input-bordered w-full font-mono text-xs",
            "placeholder": "1.3.6.1.4.1.311.20.2.2, 1.3.6.1.4.1.311.10.3.4",
        }),
        help_text="Advanced — comma-separated dotted OIDs for EKUs not in the list above. Leave blank if you don't need them.",
    )

    class Meta:
        model = CertTemplate
        fields = [
            "name", "slug", "description",
            "default_lifetime_days", "min_lifetime_days", "max_lifetime_days",
            "extended_key_usages", "key_usages", "custom_eku_oids",
        ]
        widgets = {
            "name":        forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "slug":        forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "description": forms.Textarea(attrs={"class": "textarea textarea-bordered w-full", "rows": 3}),
            "default_lifetime_days": forms.NumberInput(attrs={"class": "input input-bordered w-full", "min": 1, "max": 825}),
            "min_lifetime_days":     forms.NumberInput(attrs={"class": "input input-bordered w-full", "min": 1, "max": 825}),
            "max_lifetime_days":     forms.NumberInput(attrs={"class": "input input-bordered w-full", "min": 1, "max": 825}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # System templates can't have their slug changed — it's the stable
        # identifier load_default() looks up by.
        if self.instance and self.instance.pk and self.instance.is_system:
            self.fields["slug"].disabled = True
            self.fields["slug"].help_text = (
                "System template — slug is locked because internal lookups "
                "reference it by this exact value."
            )
        # custom_eku_oids is stored as a JSONField list on the model but
        # rendered as a comma-separated text input on the form. Reverse the
        # serialisation for the edit-page initial value.
        if self.instance and self.instance.pk and self.instance.custom_eku_oids:
            self.initial["custom_eku_oids"] = ", ".join(self.instance.custom_eku_oids)

    def clean_slug(self):
        raw = self.cleaned_data.get("slug") or ""
        slug = slugify(raw)
        if not slug:
            slug = slugify(self.cleaned_data.get("name", ""))
        if not slug:
            raise forms.ValidationError("Provide a name or slug.")
        return slug

    def clean_custom_eku_oids(self):
        raw = (self.cleaned_data.get("custom_eku_oids") or "").strip()
        if not raw:
            return []
        oids = [o.strip() for o in raw.split(",") if o.strip()]
        for oid in oids:
            if not _OID_RE.match(oid):
                raise forms.ValidationError(
                    f"'{oid}' is not a valid dotted OID (expected something "
                    f"like 1.3.6.1.4.1.311.20.2.2)."
                )
        return oids

    def clean(self):
        cleaned = super().clean()
        d = cleaned.get("default_lifetime_days") or 0
        mn = cleaned.get("min_lifetime_days") or 0
        mx = cleaned.get("max_lifetime_days") or 0
        if d < mn:
            raise forms.ValidationError("Default lifetime can't be less than the minimum.")
        if d > mx:
            raise forms.ValidationError("Default lifetime can't exceed the maximum.")
        if mn > mx:
            raise forms.ValidationError("Minimum can't exceed maximum.")
        return cleaned
