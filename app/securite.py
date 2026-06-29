"""Authentification renforcée (HTTP Basic) : mot de passe haché, anti-force-brute, journal d'audit.

L'authentification est activée dès que `GB_PASSWORD` **ou** `GB_PASSWORD_HASH` est défini.
- `GB_PASSWORD_HASH` (recommandé en production) : empreinte PBKDF2-SHA256 (voir scripts/hash_password.py),
  le mot de passe en clair n'est jamais stocké.
- `GB_PASSWORD` : mot de passe en clair (pratique en dev).
Protection anti-force-brute : au-delà de `_MAX_ECHECS` échecs récents par adresse IP, l'accès est
temporairement bloqué (HTTP 429). Les échecs et blocages sont journalisés (audit).
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import time

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.config import get_reglages

logger = logging.getLogger("uvicorn.error")
_basic = HTTPBasic(auto_error=False)

# --- Anti-force-brute (par IP, en mémoire ; suffisant pour un worker unique) ---
_MAX_ECHECS = 8
_BLOCAGE_S = 300  # fenêtre ET durée de blocage : 5 minutes
_echecs: dict[str, list[float]] = {}

# --- Hachage PBKDF2 ---
_ITERATIONS = 200_000


def hacher(mot_de_passe: str) -> str:
    """Renvoie une empreinte `pbkdf2_sha256$iterations$sel$hash`."""
    sel = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", mot_de_passe.encode("utf-8"), bytes.fromhex(sel), _ITERATIONS).hex()
    return f"pbkdf2_sha256${_ITERATIONS}${sel}${h}"


def verifier_hash(mot_de_passe: str, stocke: str) -> bool:
    """Vérifie un mot de passe contre une empreinte PBKDF2 (comparaison à temps constant)."""
    try:
        algo, iterations, sel, attendu = stocke.split("$")
        if algo != "pbkdf2_sha256":
            return False
        calc = hashlib.pbkdf2_hmac(
            "sha256", mot_de_passe.encode("utf-8"), bytes.fromhex(sel), int(iterations)
        ).hex()
        return hmac.compare_digest(calc, attendu)
    except (ValueError, AttributeError):
        return False


def auth_configuree() -> bool:
    """L'authentification est-elle activée (clair ou haché) ?"""
    r = get_reglages()
    return bool(r.mot_de_passe or r.mot_de_passe_hash)


def _identifiants_valides(utilisateur: str, mot_de_passe: str) -> bool:
    r = get_reglages()
    user_ok = hmac.compare_digest(utilisateur.encode("utf-8"), r.utilisateur.encode("utf-8"))
    if r.mot_de_passe_hash:
        pwd_ok = verifier_hash(mot_de_passe, r.mot_de_passe_hash)
    elif r.mot_de_passe:
        pwd_ok = hmac.compare_digest(mot_de_passe.encode("utf-8"), r.mot_de_passe.encode("utf-8"))
    else:
        pwd_ok = False
    return user_ok and pwd_ok


def _bloque(ip: str) -> bool:
    maintenant = time.time()
    recents = [t for t in _echecs.get(ip, []) if maintenant - t < _BLOCAGE_S]
    _echecs[ip] = recents
    return len(recents) >= _MAX_ECHECS


def _echec(ip: str) -> None:
    _echecs.setdefault(ip, []).append(time.time())


def _reset(ip: str) -> None:
    _echecs.pop(ip, None)


def exiger_auth(
    request: Request, credentials: HTTPBasicCredentials | None = Depends(_basic)
) -> None:
    """Dépendance globale : laisse passer si l'auth est désactivée, sinon vérifie + anti-brute-force."""
    if not auth_configuree():
        return

    ip = request.client.host if request.client else "inconnu"
    if _bloque(ip):
        logger.warning("AUDIT auth: accès bloqué (trop de tentatives) depuis %s", ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de tentatives. Réessayez dans quelques minutes.",
            headers={"Retry-After": str(_BLOCAGE_S)},
        )

    non_authentifie = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentification requise.",
        headers={"WWW-Authenticate": "Basic"},
    )
    if credentials is None:
        raise non_authentifie
    if _identifiants_valides(credentials.username, credentials.password):
        _reset(ip)
        return

    _echec(ip)
    logger.warning(
        "AUDIT auth: échec (utilisateur « %s ») depuis %s", credentials.username, ip
    )
    raise non_authentifie
