from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import render
from django.views import View

from apps.issuance.models import IssuedCertificate


class CertificateDetailView(LoginRequiredMixin, View):
    template_name = "issuance/detail.html"
    
    def get(self, request, pk):
        try:
            certificate = IssuedCertificate.objects.select_related(
                'template', 'signed_by'
            ).get(pk=pk)
        except IssuedCertificate.DoesNotExist:
            raise Http404("Certificate not found")
        
        # Parse the certificate PEM for display
        import cryptography.x509
        try:
            cert_obj = cryptography.x509.load_pem_x509_certificate(
                certificate.certificate_pem.encode('utf-8')
            )
            cert_details = {
                'version': cert_obj.version.name,
                'serial': format(cert_obj.serial_number, 'X'),
                'signature_algorithm': cert_obj.signature_algorithm_oid._name,
                'issuer': str(cert_obj.issuer),
                'subject': str(cert_obj.subject),
                'not_before': cert_obj.not_valid_before_utc,
                'not_after': cert_obj.not_valid_after_utc,
            }
            
            # Get extensions
            try:
                san_ext = cert_obj.extensions.get_extension_for_oid(
                    cryptography.x509.oid.ExtensionOID.SUBJECT_ALTERNATIVE_NAME
                )
                cert_details['sans'] = [str(name) for name in san_ext.value]
            except cryptography.x509.ExtensionNotFound:
                cert_details['sans'] = []
            
            try:
                eku_ext = cert_obj.extensions.get_extension_for_oid(
                    cryptography.x509.oid.ExtensionOID.EXTENDED_KEY_USAGE
                )
                cert_details['ekus'] = [eku.dotted_string for eku in eku_ext.value]
            except cryptography.x509.ExtensionNotFound:
                cert_details['ekus'] = []
            
            try:
                ku_ext = cert_obj.extensions.get_extension_for_oid(
                    cryptography.x509.oid.ExtensionOID.KEY_USAGE
                )
                ku_value = ku_ext.value
                ku_map = {
                    0: "digitalSignature",
                    1: "contentCommitment",
                    2: "keyEncipherment",
                    3: "dataEncipherment",
                    4: "keyAgreement",
                    5: "keyCertSign",
                    6: "cRLSign",
                }
                cert_details['kus'] = [
                    name for bit, name in ku_map.items()
                    if hasattr(ku_value, name) and getattr(ku_value, name)
                ]
            except cryptography.x509.ExtensionNotFound:
                cert_details['kus'] = []
                
        except Exception as e:
            cert_details = {'error': str(e)}
        
        # Determine certificate status
        from django.utils import timezone
        from datetime import timedelta
        thirty_days_from_now = timezone.now() + timedelta(days=30)
        
        if timezone.now() > certificate.not_after:
            status = 'expired'
            status_text = 'Expired'
            status_class = 'error'
        elif certificate.not_after < thirty_days_from_now:
            status = 'expiring'
            status_text = 'Expiring Soon'
            status_class = 'warning'
        else:
            status = 'valid'
            status_text = 'Valid'
            status_class = 'success'
        
        return render(request, self.template_name, {
            'certificate': certificate,
            'cert_details': cert_details,
            'status': status,
            'status_text': status_text,
            'status_class': status_class,
        })
