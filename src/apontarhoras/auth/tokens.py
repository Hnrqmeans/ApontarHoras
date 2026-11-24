"""Token de sessão (vai no cookie) e token anti-CSRF dos formulários.

No banco fica só o SHA-256 do token: quem ler o arquivo do banco não consegue usar as sessões.
"""

import hashlib
import hmac
import secrets


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def csrf_for(token: str) -> str:
    """Derivado do token da sessão: outro site não tem como adivinhar."""
    return hashlib.sha256(b"csrf:" + token.encode("utf-8")).hexdigest()[:40]


def csrf_matches(token: str, received: str) -> bool:
    return hmac.compare_digest(csrf_for(token), received)
