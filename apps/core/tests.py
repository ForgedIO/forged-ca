"""Tier 1 smoke tests: every no-arg page renders without a 500.

Why this file exists: 20 of ForgedCA's first 79 commits were page-render
breakage (TemplateSyntaxError, NoReverseMatch, redirect loops, leaked template
comments). Each would have been caught by visiting the page and asserting it
renders. See .claude/skills/test-forgedca/SKILL.md.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import URLPattern, URLResolver, get_resolver, reverse

from apps.nodes.models import NodeConfig

# Prefixes we never walk: Django's own admin, and anything whose GET has side
# effects or streams a file.
SKIP_PREFIXES = ("admin/", "acme/", "api/")


def all_named_urls():
    """Every reversible URL that takes no arguments."""
    out = []

    def walk(patterns, prefix=""):
        for p in patterns:
            if isinstance(p, URLResolver):
                walk(p.url_patterns, prefix + str(p.pattern))
            elif isinstance(p, URLPattern) and p.name:
                if not p.pattern.regex.groups:
                    out.append(prefix + str(p.pattern))

    walk(get_resolver().url_patterns)
    return out


class SmokeTestCase(TestCase):
    """An admin fully through onboarding, on a fully configured node.

    Three middleware layers redirect an authenticated user away from almost
    every page. Miss any and assertions pass against a 302, proving nothing.
    """

    def setUp(self):
        user = get_user_model().objects.create_user("smoke", password="x")
        profile = user.profile
        profile.must_change_password = False
        profile.mfa_enabled = True
        profile.save()

        config = NodeConfig.load()
        config.is_root = True
        config.is_intermediate = True
        config.is_issuing = True
        config.is_configured = True
        config.hostname = "ca.test.local"
        config.save()

        self.client.force_login(user)
        self.user = user
        self.config = config


class AllPagesRenderTest(SmokeTestCase):
    def test_no_page_returns_5xx(self):
        failures = []
        for path in all_named_urls():
            if path.startswith(SKIP_PREFIXES):
                continue
            url = "/" + path
            try:
                response = self.client.get(url, follow=True)
            except Exception as exc:  # template/view errors surface here
                failures.append(f"{url} raised {type(exc).__name__}: {exc}")
                continue
            if response.status_code >= 500:
                failures.append(f"{url} -> {response.status_code}")
        self.assertEqual(failures, [], "pages failed to render:\n" + "\n".join(failures))


class IssuancePagesTest(SmokeTestCase):
    """Covers the templates currently being edited."""

    def test_issuance_index_renders(self):
        response = self.client.get(reverse("issuance:index"), follow=True)
        self.assertEqual(response.status_code, 200)

    def test_csr_sign_page_renders(self):
        response = self.client.get(reverse("issuance:sign"), follow=True)
        self.assertEqual(response.status_code, 200)


class MiddlewareGatesTest(TestCase):
    """The gates must actually gate; otherwise the suite proves nothing."""

    def test_unonboarded_user_is_redirected_away_from_pages(self):
        user = get_user_model().objects.create_user("fresh", password="x")
        self.client.force_login(user)
        response = self.client.get(reverse("issuance:index"))
        self.assertEqual(response.status_code, 302)
