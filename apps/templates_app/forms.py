from django import forms
from django.utils.text import slugify

from .models import CertTemplate


class CertTemplateForm(forms.ModelForm):
    class Meta:
        model = CertTemplate
        fields = [
            "name", "slug", "description",
            "default_lifetime_days", "min_lifetime_days", "max_lifetime_days",
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

    def clean_slug(self):
        raw = self.cleaned_data.get("slug") or ""
        slug = slugify(raw)
        if not slug:
            slug = slugify(self.cleaned_data.get("name", ""))
        if not slug:
            raise forms.ValidationError("Provide a name or slug.")
        return slug

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
