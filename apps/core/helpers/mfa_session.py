"""Session-backed state for the post-login MFA challenge flow."""
import time

from django.contrib.auth import get_user_model


CHALLENGE_TTL_SECONDS = 300
MAX_ATTEMPTS = 5
SESSION_KEYS = ("mfa_user_id", "mfa_next", "mfa_expires", "mfa_attempts")


User = get_user_model()


def start_challenge(request, user, next_url: str) -> None:
    request.session["mfa_user_id"] = user.pk
    request.session["mfa_next"] = next_url
    request.session["mfa_expires"] = time.time() + CHALLENGE_TTL_SECONDS
    request.session["mfa_attempts"] = 0


def pending_user(request):
    user_id = request.session.get("mfa_user_id")
    expires = request.session.get("mfa_expires", 0)
    if not user_id or time.time() > expires:
        clear_challenge(request)
        return None
    try:
        return User.objects.get(pk=user_id, is_active=True)
    except User.DoesNotExist:
        clear_challenge(request)
        return None


def record_attempt(request) -> int:
    count = request.session.get("mfa_attempts", 0) + 1
    request.session["mfa_attempts"] = count
    return count


def clear_challenge(request) -> None:
    for key in SESSION_KEYS:
        request.session.pop(key, None)


def complete_challenge(request) -> str:
    """Return the stashed next_url and clear all challenge state."""
    next_url = request.session.get("mfa_next", "/")
    clear_challenge(request)
    return next_url
