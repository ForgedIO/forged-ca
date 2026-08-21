from django import forms
from django.core.files.uploadedfile import UploadedFile

class CsrSignForm(forms.Form):
    """Form for CSR input - paste or upload."""
    
    csr_source = forms.ChoiceField(
        choices=[
            ("paste", "Paste CSR"),
            ("upload", "Upload CSR file"),
        ],
        widget=forms.RadioSelect,
        initial="paste",
        label="CSR input method",
    )
    
    csr_paste = forms.CharField(
        widget=forms.Textarea(attrs={
            "rows": 15,
            "placeholder": "Paste your CSR here (-----BEGIN CERTIFICATE REQUEST-----)...",
        }),
        required=False,
        label="CSR (pasted)",
    )
    
    csr_file = forms.FileField(
        widget=forms.ClearableFileInput(attrs={"accept": ".csr,.pem"}),
        required=False,
        label="CSR file (.csr or .pem)",
    )
    
    template = forms.ModelChoiceField(
        queryset=None,
        empty_label=None,
        label="Certificate template",
        help_text="Policy template to apply to this certificate.",
    )
    
    passthrough = forms.BooleanField(
        required=False,
        label="Passthrough (advanced)",
        help_text="Bypass template policy and sign exactly what was requested. Use only if you know what you're doing.",
        widget=forms.CheckboxInput(attrs={"class": "alert-warning"}),
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.templates_app.models import CertTemplate
        self.fields["template"].queryset = CertTemplate.objects.all().order_by("-is_system", "name")
    
    def clean(self):
        cleaned_data = super().clean()
        source = cleaned_data.get("csr_source")
        
        if source == "paste":
            csr_paste = cleaned_data.get("csr_paste")
            if not csr_paste or not csr_paste.strip():
                raise forms.ValidationError("Please paste a CSR or upload a file.")
        elif source == "upload":
            csr_file = cleaned_data.get("csr_file")
            if not csr_file:
                raise forms.ValidationError("Please upload a CSR file.")
        
        return cleaned_data
    
    def get_csr_pem(self) -> str:
        source = self.cleaned_data.get("csr_source")
        if source == "paste":
            return self.cleaned_data["csr_paste"]
        else:
            uploaded_file = self.cleaned_data["csr_file"]
            return uploaded_file.read().decode("utf-8")

class CsrSignConfirmForm(forms.Form):
    """Form for confirming signing - passes data from previous step."""
    
    # This form doesn't have any fields - it's just used for the confirmation page
    # The actual data comes from the previous step
    pass
