from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, Http404
from django.views import View

from apps.issuance.models import IssuedCertificate


class CertificateDownloadView(LoginRequiredMixin, View):
    """Download certificate in PEM format."""
    
    def get(self, request, pk):
        try:
            certificate = IssuedCertificate.objects.get(pk=pk)
        except IssuedCertificate.DoesNotExist:
            raise Http404("Certificate not found")
        
        # Determine what to download
        download_type = request.GET.get('type', 'leaf')
        
        if download_type == 'leaf':
            # Download just the leaf certificate
            cert_pem = certificate.certificate_pem
            filename = f"{certificate.filename_stem}.crt"
        elif download_type == 'fullchain':
            # Download full certificate chain
            cert_pem = certificate.get_fullchain_pem()
            filename = f"{certificate.filename_stem}-fullchain.crt"
        else:
            raise Http404("Invalid download type")
        
        # Return as downloadable file
        response = HttpResponse(cert_pem, content_type='application/x-pem-file')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
