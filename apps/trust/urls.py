from django.urls import path

from . import views

app_name = "trust"

urlpatterns = [
    path("root.crt", views.root_crt, name="root_crt"),
    path("intermediate.crt", views.intermediate_crt, name="intermediate_crt"),
    path("issuer.crt", views.issuer_crt, name="issuer_crt"),
    path("chain.pem", views.chain_pem, name="chain_pem"),
    path("bundle.crt", views.bundle_crt, name="bundle_crt"),
]
