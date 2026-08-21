from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import redirect, render
from django.views import View

from apps.issuance.forms import CsrSignForm
from apps.issuance.helpers.csr import parse_csr, CsrError
from apps.issuance.helpers.policy import validate_csr_policy, CsrValidationError
from apps.issuance.helpers.signer import sign_csr, SignerError
from apps.issuance.models import IssuedCertificate
from apps.nodes.models import NodeConfig
from apps.templates_app.models import CertTemplate


class CsrSignView(LoginRequiredMixin, View):
    template_name = "issuance/sign.html"
    step = 1
    step_label = "Sign Certificate from CSR"
    
    def get(self, request):
        form = CsrSignForm()
        return render(request, self.template_name, self._context(form))
    
    def post(self, request):
        form = CsrSignForm(request.POST, request.FILES)
        
        if not form.is_valid():
            return render(request, self.template_name, self._context(form))
        
        # Parse the CSR
        csr_pem = form.get_csr_pem()
        try:
            parsed = parse_csr(csr_pem)
        except CsrError as e:
            messages.error(request, str(e))
            return render(request, self.template_name, self._context(form))
        
        # Get template
        template = form.cleaned_data["template"]
        is_passthrough = form.cleaned_data.get("passthrough", False)
        
        # Validate against template
        reasons = validate_csr_policy(parsed, template)
        
        if reasons and not is_passthrough:
            messages.error(
                request,
                f"This CSR cannot be signed with the selected template." 
                f"{chr(10).join(reasons)}"
            )
            return render(request, self.template_name, self._context(form, parsed, template))
        
        # If passthrough, warn user
        if is_passthrough:
            messages.warning(
                request,
                "Passthrough mode enabled: signing exactly what was requested." 
                "CA bits are still rejected for safety."
            )
        
        # Show preview page
        return render(request, self.template_name, self._context(
            form, parsed, template, is_passthrough=True, show_preview=True
        ))
    
    def _context(self, form, parsed=None, template=None, is_passthrough=False, show_preview=False):
        context = {
            "form": form,
            "step": self.step,
            "step_label": self.step_label,
            "show_preview": show_preview,
            "is_passthrough": is_passthrough,
        }
        
        if parsed:
            context["parsed_csr"] = parsed
            context["parsed_csr"].eku_labels = [
                self._eku_label(eku) for eku in parsed.requested_ekus
            ]
            context["parsed_csr"].ku_labels = parsed.requested_kus
        
        if template:
            context["template"] = template
            context["template"].eku_labels = template.eku_short_labels
            context["template"].ku_labels = template.key_usages
            
            if parsed:
                reasons = validate_csr_policy(parsed, template)
                if reasons:
                    context["validation_errors"] = reasons
        
        return context
    
    def _eku_label(self, eku):
        from apps.templates_app.models import EKU_SHORT_LABELS
        return EKU_SHORT_LABELS.get(eku, eku)

class CsrSignConfirmView(LoginRequiredMixin, View):
    template_name = "issuance/sign.html"
    
    def post(self, request):
        csr_pem = request.POST.get("csr_pem")
        template_id = request.POST.get("template_id")
        is_passthrough = request.POST.get("passthrough") == "1"
        
        if not csr_pem or not template_id:
            messages.error(request, "Missing CSR or template data.")
            return redirect("issuance:sign")
        
        try:
            # Parse the CSR
            parsed = parse_csr(csr_pem)
            
            # Get the template
            try:
                template = CertTemplate.objects.get(id=template_id)
            except CertTemplate.DoesNotExist:
                messages.error(request, "Template not found.")
                return redirect("issuance:sign")
            
            # Validate policy (but allow passthrough to override)
            if not is_passthrough:
                reasons = validate_csr_policy(parsed, template)
                if reasons:
                    error_msg = f"This CSR cannot be signed with the selected template.\n\n" + "\n".join(reasons)
                    messages.error(request, error_msg)
                    return render(request, self.template_name, {
                        "form": CsrSignForm(),
                        "parsed_csr": parsed,
                        "template": template,
                        "validation_errors": reasons,
                        "show_preview": True,
                    })
            
            # Sign the certificate
            cert_pem, metadata = sign_csr(csr_pem, template, is_passthrough)
            
            # Save to database
            cert = IssuedCertificate.objects.create(
                serial=metadata['serial'],
                common_name=metadata['common_name'],
                sans="\n".join(metadata['sans']) if metadata['sans'] else "",
                template=template if not is_passthrough else None,
                template_name=template.name if not is_passthrough else "Passthrough",
                is_passthrough=is_passthrough,
                extended_key_usages=metadata['extended_key_usages'],
                key_usages=metadata['key_usages'],
                not_before=metadata['not_before'],
                not_after=metadata['not_after'],
                signer_tier=metadata['signer_tier'],
                source="manual",
                certificate_pem=cert_pem,
                csr_pem=csr_pem,
                signed_by=request.user,
                csr=None,  # csr field is actually a FK to user - we use csr_pem instead
            )
            
            messages.success(
                request,
                f"Certificate issued successfully! Serial: {metadata['serial']}"
            )
            return redirect("issuance:detail", pk=cert.id)
            
        except CsrError as e:
            messages.error(request, f"CSR parsing error: {str(e)}")
            return redirect("issuance:sign")
        except SignerError as e:
            messages.error(request, f"Signing failed: {str(e)}")
            return redirect("issuance:sign")
        except Exception as e:
            messages.error(request, f"Unexpected error: {str(e)}")
            return redirect("issuance:sign")
