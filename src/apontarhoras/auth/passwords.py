"""Hash de senha com scrypt (hashlib). A senha nunca é guardada nem registrada em texto."""

import base64
import hashlib
import hmac
import secrets
from functools import cache

_N = 2**14
_R = 8
_P = 1
_KEY_LENGTH = 32


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=_KEY_LENGTH)
    return f"scrypt${_N}${_R}${_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(digest)
        actual = hashlib.scrypt(
            password.encode("utf-8"), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=len(expected)
        )
    except ValueError:
        return False
    return hmac.compare_digest(actual, expected)


@cache
def dummy_hash() -> str:
    """Hash descartável: login inexistente gasta o mesmo tempo que senha errada (não revela quem existe)."""
    return hash_password(secrets.token_urlsafe(16))
