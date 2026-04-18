from django.urls import path

from .views import (
    BundleCrtView,
    ChainPemView,
    IntermediateCrtView,
    IssuerCrtView,
    RootCrtView,
)


app_name = "trust"


urlpatterns = [
    path("root.crt", RootCrtView.as_view(), name="root_crt"),
    path("intermediate.crt", IntermediateCrtView.as_view(), name="intermediate_crt"),
    path("issuer.crt", IssuerCrtView.as_view(), name="issuer_crt"),
    path("chain.pem", ChainPemView.as_view(), name="chain_pem"),
    path("bundle.crt", BundleCrtView.as_view(), name="bundle_crt"),
]
