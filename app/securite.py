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
    """Auth activée si un mot de passe est défini dans .env OU si des comptes existent en base."""
    r = get_reglages()
    if r.mot_de_passe or r.mot_de_passe_hash:
        return True
    from app import db  # import tardif (db n'importe jamais securite)

    try:
        return db.utilisateurs_actifs_existent()
    except Exception:  # noqa: BLE001 — une base indisponible ne doit pas ouvrir l'accès… ni le bloquer au boot
        return False


def _authentifier(utilisateur: str, mot_de_passe: str) -> tuple[str, str] | None:
    """Renvoie (identifiant, rôle) si les identifiants sont valides, sinon None.

    Les comptes nominatifs (base) priment ; le compte unique du .env reste accepté
    (compatibilité + secours), avec le rôle admin.
    """
    from app import db

    try:
        compte = db.lire_utilisateur(utilisateur)
    except Exception:  # noqa: BLE001
        compte = None
    if compte and verifier_hash(mot_de_passe, compte["hash"]):
        return compte["identifiant"], compte["role"]

    r = get_reglages()
    user_ok = hmac.compare_digest(utilisateur.encode("utf-8"), r.utilisateur.encode("utf-8"))
    if r.mot_de_passe_hash:
        pwd_ok = verifier_hash(mot_de_passe, r.mot_de_passe_hash)
    elif r.mot_de_passe:
        pwd_ok = hmac.compare_digest(mot_de_passe.encode("utf-8"), r.mot_de_passe.encode("utf-8"))
    else:
        pwd_ok = False
    if user_ok and pwd_ok:
        return r.utilisateur, "admin"
    return None


def _bloque(ip: str) -> bool:
    maintenant = time.time()
    recents = [t for t in _echecs.get(ip, []) if maintenant - t < _BLOCAGE_S]
    _echecs[ip] = recents
    return len(recents) >= _MAX_ECHECS


def _echec(ip: str) -> None:
    _echecs.setdefault(ip, []).append(time.time())


def _reset(ip: str) -> None:
    _echecs.pop(ip, None)


def utilisateur_courant(request: Request) -> str:
    """Identifiant authentifié porté par la requête (« poste-local » quand l'auth est désactivée)."""
    return getattr(request.state, "utilisateur", "poste-local")


def exiger_admin(request: Request) -> None:
    """Réserve une route aux administrateurs (tout est admin quand l'auth est désactivée)."""
    if getattr(request.state, "role", "admin") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Action réservée aux administrateurs.",
        )


def exiger_auth(
    request: Request, credentials: HTTPBasicCredentials | None = Depends(_basic)
) -> None:
    """Dépendance globale : laisse passer si l'auth est désactivée, sinon vérifie + anti-brute-force."""
    if not auth_configuree():
        request.state.utilisateur = "poste-local"
        request.state.role = "admin"
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
    resultat = _authentifier(credentials.username, credentials.password)
    if resultat:
        request.state.utilisateur, request.state.role = resultat
        _reset(ip)
        return

    _echec(ip)
    # On ne journalise PAS l'identifiant saisi : un mot de passe tapé par erreur dans le champ
    # « utilisateur » finirait en clair dans les logs (minimisation, art. 5 RGPD).
    logger.warning("AUDIT auth: échec d'authentification depuis %s", ip)
    raise non_authentifie
