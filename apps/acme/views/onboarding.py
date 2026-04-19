from urllib.parse import urlparse

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.urls import reverse
from django.views import View

from apps.ca import daemon
from apps.ca.helpers.fingerprint import cert_sha256
from apps.nodes.models import NodeConfig

from ..models import ACMEProvisioner


class AcmeOnboardingView(LoginRequiredMixin, View):
    """Read-only 'how to enrol a client against this CA' reference.

    One page that substitutes the hostname, ACME directory URL, Root
    fingerprint, and trust-bundle URL into copy-paste blocks for every
    popular ACME client. The admin can link this page to a dev team or
    an appliance installer without granting admin access to the CA UI
    itself — once it's behind a non-admin perm check in a later slice.
    """
    template_name = "acme/onboarding.html"

    def get(self, request):
        config = NodeConfig.load()
        provisioner = ACMEProvisioner.load()

        # build_absolute_uri reflects whatever host/port the admin browsed to.
        # Good enough for trust-download links (served by nginx on :8443 or
        # whatever port WEB_PORT is set to). The ACME directory URL is always
        # on :9000 because step-ca owns that port; don't conflate the two.
        admin_base = request.build_absolute_uri("/").rstrip("/")
        admin_host = urlparse(admin_base).hostname or config.hostname or "localhost"

        # The ACME / step-ca URL uses step-ca's dnsNames (config.hostname), not
        # whatever the admin hit — admins usually hit the IP during setup but
        # clients need the real DNS name step-ca put in the cert.
        ca_host = config.hostname or admin_host
        ca_url = f"https://{ca_host}:9000"

        root_fp = cert_sha256(config.root_cert_path) if config.root_cert_path else ""

        return render(request, self.template_name, {
            "config": config,
            "provisioner": provisioner,
            "ca_url": ca_url,
            "ca_host": ca_host,
            "directory_url": provisioner.directory_url(ca_host),
            "root_fingerprint": root_fp,
            "root_download_url":   admin_base + reverse("trust:root_crt"),
            "bundle_download_url": admin_base + reverse("trust:bundle_crt"),
            "chain_download_url":  admin_base + reverse("trust:chain_pem"),
            "step_ca": daemon.status() if config.is_issuing else None,
            # A sample DNS name we use in every snippet so the admin can
            # search-replace one string.
            "sample_host": f"service.{ca_host.split('.', 1)[-1]}" if "." in ca_host else "host.lab.local",
        })
