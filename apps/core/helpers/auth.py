"""Auth helpers shared by the login view."""
from django.contrib.auth import get_user_model


User = get_user_model()


def resolve_username(raw: str) -> str:
    """Let users log in with email — look up the username for an email input,
    or return the input unchanged if it's not an email or no match exists."""
    if "@" not in raw:
        return raw
    try:
        return User.objects.get(email__iexact=raw).username
    except User.DoesNotExist:
        return raw


def safe_next_url(request, fallback: str = "/") -> str:
    """Return a redirect target that can't escape the app."""
    next_url = request.POST.get("next") or request.GET.get("next") or fallback
    return next_url if next_url.startswith("/") else fallback
