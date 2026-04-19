"""Manage the CA signing-key passphrase + its on-disk password file.

step-ca expects one password that decrypts every CA key (Root, Intermediate,
Issuing). We mint that password once per node on first use, write it to
/etc/step-ca/secrets/password.txt with mode 0640 (step-ca group-readable),
and reuse it for every `step certificate create --password-file=…` and for
step-ca's ExecStart.

At-rest threat model:
  * Root on the box → can read both the password file and the encrypted
    keys, so full compromise. This matches every single-host PKI stack.
  * Any other user (including via misconfigured backup job, container
    mount leak, non-root SSH account) → mode 0640 keeps them out of
    password.txt. An encrypted PEM key exfiltrated alone is useless.
  * Disk image theft with no key material decryption → encrypted keys
    protect the CA even if the filesystem is read off a dd'd image.
"""
import os
import secrets
import string
from pathlib import Path

from django.conf import settings


def _password_path() -> Path:
    return Path(settings.STEP_CA_CONFIG_DIR) / "secrets" / "password.txt"


def exists() -> bool:
    return _password_path().is_file()


def read() -> str:
    """Return the CA password. Callers must ensure() first on a fresh node."""
    return _password_path().read_text().rstrip("\n")


def ensure(length: int = 48) -> str:
    """Write a random CA password if one doesn't already exist, return it.

    Alphanumeric only — avoids quoting pain when we're reading/writing the
    file and when step-cli echoes the passphrase in error messages. 48
    chars ≈ 285 bits of entropy; way past any brute-force threshold.
    """
    path = _password_path()
    if path.is_file():
        return read()

    alphabet = string.ascii_letters + string.digits
    password = "".join(secrets.choice(alphabet) for _ in range(length))

    path.parent.mkdir(parents=True, exist_ok=True)
    # Write with mode 0640 so step-ca (member of the step-ca group) can read
    # but no other local user can. Use an atomic rename so a crash mid-write
    # never leaves us with an empty / partial password.
    tmp = path.with_suffix(".new")
    tmp.write_text(password + "\n")
    os.chmod(tmp, 0o640)
    tmp.replace(path)
    return password
