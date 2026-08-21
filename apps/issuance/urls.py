from django.urls import path

from .views import IssuanceIndexView, CsrSignView, CertificateDetailView, CertificateDownloadView


app_name = "issuance"


urlpatterns = [
    path("", IssuanceIndexView.as_view(), name="index"),
    path("sign/", CsrSignView.as_view(), name="sign"),
    path("detail/<int:pk>/", CertificateDetailView.as_view(), name="detail"),
    path("download/<int:pk>/", CertificateDownloadView.as_view(), name="download"),
]
