"""TOTP and recovery-code primitives. Pure functions unless noted."""
import hashlib
import io
import json
import secrets
from base64 import b64encode

import pyotp
import qrcode


RECOVERY_CODE_COUNT = 8
TOTP_VALID_WINDOW = 1
SESSION_PENDING_SECRET_KEY = "mfa_pending_secret"


def hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def generate_recovery_codes(count: int = RECOVERY_CODE_COUNT) -> tuple[list[str], str]:
    codes = [secrets.token_hex(4) for _ in range(count)]
    hashed_json = json.dumps([hash_code(c) for c in codes])
    return codes, hashed_json


def verify_totp(secret: str, code: str) -> bool:
    if not secret or not code:
        return False
    if len(code) != 6 or not code.isdigit():
        return False
    return pyotp.TOTP(secret).verify(code, valid_window=TOTP_VALID_WINDOW)


def consume_recovery_code(profile, code: str) -> bool:
    """Mutates: on match, removes the hash from storage and saves."""
    try:
        stored = json.loads(profile.mfa_recovery_codes or "[]")
    except (ValueError, TypeError):
        return False
    code_hash = hash_code(code.lower())
    if code_hash not in stored:
        return False
    stored.remove(code_hash)
    profile.mfa_recovery_codes = json.dumps(stored)
    profile.save(update_fields=["mfa_recovery_codes"])
    return True


def get_or_create_pending_secret(request) -> str:
    secret = request.session.get(SESSION_PENDING_SECRET_KEY)
    if not secret:
        secret = pyotp.random_base32()
        request.session[SESSION_PENDING_SECRET_KEY] = secret
    return secret


def read_pending_secret(request) -> str | None:
    return request.session.get(SESSION_PENDING_SECRET_KEY)


def clear_pending_secret(request) -> None:
    request.session.pop(SESSION_PENDING_SECRET_KEY, None)


def provisioning_qr_data_uri(secret: str, name: str, issuer: str) -> str:
    uri = pyotp.TOTP(secret).provisioning_uri(name=name, issuer_name=issuer)
    img = qrcode.make(uri, box_size=6, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + b64encode(buf.getvalue()).decode()
