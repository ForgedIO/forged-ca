"""Authentication and account-lifecycle views.

Covers: login (with MFA branch), logout, home, forced password change, TOTP
enrollment, TOTP verification, and recovery-code consumption. Slice 1.5 scope
\u2014 password reset via email, Entra-specific skip, and email-bypass recovery
all belong to later slices.
"""
import hashlib
import io
import json
import logging
import secrets
import time
from base64 import b64encode

import pyotp
import qrcode
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.nodes.models import NodeConfig


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MFA_SESSION_KEYS = ("mfa_user_id", "mfa_next", "mfa_expires", "mfa_attempts")
MFA_CHALLENGE_TTL = 300  # seconds


def _clear_mfa_session(request):
    for key in MFA_SESSION_KEYS:
        request.session.pop(key, None)


def _get_mfa_pending_user(request):
    """Return the User whose MFA challenge is in progress, or None."""
    user_id = request.session.get("mfa_user_id")
    expires = request.session.get("mfa_expires", 0)
    if not user_id or time.time() > expires:
        _clear_mfa_session(request)
        return None
    try:
        return User.objects.get(pk=user_id, is_active=True)
    except User.DoesNotExist:
        _clear_mfa_session(request)
        return None


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def _generate_recovery_codes(count: int = 8) -> tuple[list[str], str]:
    """Return (plaintext list shown once to the user, JSON of hashed codes to persist)."""
    codes = [secrets.token_hex(4) for _ in range(count)]
    hashed = json.dumps([_hash_code(c) for c in codes])
    return codes, hashed


# ---------------------------------------------------------------------------
# Login / logout / home
# ---------------------------------------------------------------------------


def login_view(request):
    """Replaces Django's built-in LoginView so we can branch to the MFA
    challenge page when the user has TOTP enrolled."""
    if request.user.is_authenticated:
        return redirect("core:home")

    error = None
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        if "@" in username:
            try:
                username = User.objects.get(email__iexact=username).username
            except User.DoesNotExist:
                pass

        user = authenticate(request, username=username, password=password)
        if user is not None:
            next_url = request.POST.get("next") or request.GET.get("next") or "/"
            if not next_url.startswith("/"):
                next_url = "/"

            try:
                profile = user.profile
                if profile.mfa_enabled and profile.needs_mfa_at_login:
                    request.session["mfa_user_id"] = user.pk
                    request.session["mfa_next"] = next_url
                    request.session["mfa_expires"] = time.time() + MFA_CHALLENGE_TTL
                    request.session["mfa_attempts"] = 0
                    return redirect("core:mfa_verify")
            except Exception as e:
                logger.debug("login_view: MFA pre-check failed: %s", e)

            login(request, user)
            return redirect(next_url)
        else:
            error = "Invalid username or password."

    return render(request, "registration/login.html", {"error": error})


def logout_view(request):
    logout(request)
    return redirect("core:login")


@login_required
def home(request):
    config = NodeConfig.load()
    if not config.is_configured:
        return redirect("wizard:step_role")
    return render(request, "core/home.html", {"config": config})


# ---------------------------------------------------------------------------
# Forced password change
# ---------------------------------------------------------------------------


@login_required
def change_password(request):
    error = None
    if request.method == "POST":
        new_password = request.POST.get("new_password", "")
        confirm = request.POST.get("confirm_password", "")

        if len(new_password) < 8:
            error = "Password must be at least 8 characters."
        elif new_password != confirm:
            error = "Passwords do not match."
        elif new_password == "Password!":
            error = "Pick a password different from the default."
        else:
            request.user.set_password(new_password)
            request.user.save()
            try:
                request.user.profile.must_change_password = False
                request.user.profile.save(update_fields=["must_change_password"])
            except Exception as e:
                logger.warning("change_password: clearing flag failed: %s", e)
            update_session_auth_hash(request, request.user)
            messages.success(request, "Password updated.")
            return redirect("core:home")

    return render(request, "core/change_password.html", {"error": error})


# ---------------------------------------------------------------------------
# MFA enrollment (post-password-change, before wizard)
# ---------------------------------------------------------------------------


@login_required
def mfa_setup(request):
    """Show the authenticator QR code + pending TOTP secret. Confirm via POST."""
    profile = request.user.profile

    pending_secret = request.session.get("mfa_pending_secret")
    if not pending_secret:
        pending_secret = pyotp.random_base32()
        request.session["mfa_pending_secret"] = pending_secret

    name = request.user.email or request.user.username
    uri = pyotp.TOTP(pending_secret).provisioning_uri(name=name, issuer_name="ForgedCA")

    img = qrcode.make(uri, box_size=6, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_data_uri = "data:image/png;base64," + b64encode(buf.getvalue()).decode()

    return render(request, "core/mfa_setup.html", {
        "qr_data_uri": qr_data_uri,
        "secret": pending_secret,
        "already_enabled": profile.mfa_enabled,
    })


@login_required
@require_POST
def mfa_setup_confirm(request):
    pending_secret = request.session.get("mfa_pending_secret")
    if not pending_secret:
        messages.error(request, "MFA setup expired. Please try again.")
        return redirect("core:mfa_setup")

    code = request.POST.get("code", "").strip().replace(" ", "")
    if not pyotp.TOTP(pending_secret).verify(code, valid_window=1):
        messages.error(request, "Invalid code. Scan the QR again and enter the current 6-digit code.")
        return redirect("core:mfa_setup")

    profile = request.user.profile
    profile.mfa_secret = pending_secret
    profile.mfa_enabled = True
    profile.mfa_confirmed_at = timezone.now()
    codes, hashed_json = _generate_recovery_codes()
    profile.mfa_recovery_codes = hashed_json
    profile.save(update_fields=["mfa_secret", "mfa_enabled", "mfa_confirmed_at", "mfa_recovery_codes"])

    request.session.pop("mfa_pending_secret", None)
    logger.info("mfa_setup: enabled for user %s", request.user.username)
    return render(request, "core/mfa_recovery_codes.html", {"codes": codes})


# ---------------------------------------------------------------------------
# MFA challenge at login
# ---------------------------------------------------------------------------


def mfa_verify(request):
    user = _get_mfa_pending_user(request)
    if user is None:
        return redirect("core:login")

    error = None
    if request.method == "POST":
        code = request.POST.get("code", "").strip().replace(" ", "")
        attempts = request.session.get("mfa_attempts", 0) + 1
        request.session["mfa_attempts"] = attempts

        if attempts > 5:
            messages.error(request, "Too many failed attempts. Sign in again.")
            _clear_mfa_session(request)
            return redirect("core:login")

        verified = False

        if len(code) == 6 and code.isdigit():
            if pyotp.TOTP(user.profile.mfa_secret).verify(code, valid_window=1):
                verified = True

        if not verified and len(code) == 8:
            try:
                stored = json.loads(user.profile.mfa_recovery_codes or "[]")
                code_hash = _hash_code(code.lower())
                if code_hash in stored:
                    stored.remove(code_hash)
                    user.profile.mfa_recovery_codes = json.dumps(stored)
                    user.profile.save(update_fields=["mfa_recovery_codes"])
                    verified = True
                    logger.info("mfa_verify: user %s used recovery code (%d remaining)",
                                user.username, len(stored))
            except (ValueError, TypeError):
                pass

        if verified:
            next_url = request.session.get("mfa_next", "/")
            _clear_mfa_session(request)
            login(request, user)
            return redirect(next_url)

        error = "Invalid code. Try again."

    return render(request, "core/mfa_verify.html", {"error": error})
