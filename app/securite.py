"""Authentification renforcée : sessions par cookie signé + HTTP Basic (compatibilité),
mot de passe haché, anti-force-brute, journal d'audit.

L'authentification est activée dès que `GB_PASSWORD`/`GB_PASSWORD_HASH` est défini OU que des
comptes existent en base. Le navigateur passe par la page /connexion (cookie de session signé
HMAC, 7 jours) ; l'auth Basic reste acceptée (scripts, compatibilité, secours).
Protection anti-force-brute : au-delà de `_MAX_ECHECS` échecs récents par adresse IP, l'accès est
temporairement bloqué (HTTP 429). Derrière un proxy de confiance (GB_PROXY_CONFIANCE=1), l'IP
réelle est lue dans CF-Connecting-IP / X-Forwarded-For. Les échecs sont journalisés (audit).
"""

from __future__ import annotations

import base64
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


# --- Sessions par cookie signé (page /connexion) ---
COOKIE_SESSION = "gb_session"
_SESSION_DUREE_S = 7 * 24 * 3600  # 7 jours : le chauffeur ne retape pas son mot de passe chaque matin


def _secret_session() -> bytes:
    """Secret de signature des sessions, dans le coffre local (hors base/sauvegardes).

    Migre l'ancien emplacement (base) le cas échéant, puis purge la base de ce secret.
    """
    from app import coffre, db

    secret = coffre.lire("session")
    if secret:
        return secret.encode("utf-8")
    ancien = db.lire_parametre("secret_session")  # migration depuis les versions ≤ 2.5.0
    secret = ancien or secrets.token_hex(32)
    coffre.ecrire("session", secret)
    if ancien:
        db.ecrire_parametre("secret_session", "")  # ne plus laisser le secret dans la base
    return secret.encode("utf-8")


def _signer(donnees: str) -> str:
    return hmac.new(_secret_session(), donnees.encode("utf-8"), hashlib.sha256).hexdigest()


def _sceau_compte(identifiant: str) -> str:
    """Empreinte courte liée au mot de passe du compte : intégrée au jeton, elle **révoque**
    toutes les sessions dès que le mot de passe change (le sceau ne correspond plus)."""
    from app import db

    try:
        compte = db.lire_utilisateur(identifiant)
    except Exception:  # noqa: BLE001
        compte = None
    base = compte["hash"] if compte else ""
    if not base:
        r = get_reglages()
        if identifiant == r.utilisateur:
            base = r.mot_de_passe_hash or r.mot_de_passe or ""
    return hashlib.sha256(base.encode("utf-8") + _secret_session()).hexdigest()[:16]


def creer_session(identifiant: str) -> str:
    """Jeton de session : b64(id).expiration.sceau.signature — vérifiable sans état serveur.

    Le `sceau` lie la session au mot de passe : le réinitialiser invalide les sessions en cours.
    """
    ident_b64 = base64.urlsafe_b64encode(identifiant.encode("utf-8")).decode("ascii")
    expiration = str(int(time.time()) + _SESSION_DUREE_S)
    corps = f"{ident_b64}.{expiration}.{_sceau_compte(identifiant)}"
    return f"{corps}.{_signer(corps)}"


def valider_session(jeton: str) -> tuple[str, str] | None:
    """Renvoie (identifiant, rôle) si le jeton est signé, non expiré, le sceau (mot de passe)
    inchangé et le compte toujours actif."""
    try:
        ident_b64, expiration, sceau, signature = jeton.split(".")
        if not hmac.compare_digest(signature, _signer(f"{ident_b64}.{expiration}.{sceau}")):
            return None
        if time.time() > int(expiration):
            return None
        identifiant = base64.urlsafe_b64decode(ident_b64.encode("ascii")).decode("utf-8")
    except (ValueError, TypeError):
        return None
    # Sceau : rejette la session si le mot de passe a changé depuis son émission.
    if not hmac.compare_digest(sceau, _sceau_compte(identifiant)):
        return None
    from app import db

    try:
        compte = db.lire_utilisateur(identifiant)
    except Exception:  # noqa: BLE001
        compte = None
    if compte:
        return compte["identifiant"], compte["role"]
    # Compte du .env (secours) : accepté aussi en session.
    r = get_reglages()
    if identifiant == r.utilisateur and (r.mot_de_passe or r.mot_de_passe_hash):
        return identifiant, "admin"
    return None


def ip_client(request: Request) -> str:
    """IP réelle du client — lit X-Forwarded-For UNIQUEMENT si GB_PROXY_CONFIANCE=1.

    Derrière Caddy (kit VPS), request.client.host est l'IP du proxy : sans ce correctif,
    l'anti-force-brute bloquerait TOUT LE MONDE dès qu'un robot échoue 8 fois.

    ⚠️ On lit le DERNIER maillon de X-Forwarded-For : avec exactement un proxy de confiance
    en amont (Caddy, configuré pour réécrire l'en-tête — voir deploy/Caddyfile), c'est la seule
    valeur non falsifiable par le client. On n'honore PAS CF-Connecting-IP (en-tête propriétaire
    Cloudflare que Caddy ne pose ni ne retire : il serait librement injectable par l'attaquant).
    """
    if get_reglages().proxy_confiance:
        xff = request.headers.get("X-Forwarded-For")
        if xff:
            return xff.split(",")[-1].strip()
    return request.client.host if request.client else "inconnu"


def _bloque(ip: str) -> bool:
    maintenant = time.time()
    recents = [t for t in _echecs.get(ip, []) if maintenant - t < _BLOCAGE_S]
    _echecs[ip] = recents
    return len(recents) >= _MAX_ECHECS


def _echec(ip: str) -> None:
    _echecs.setdefault(ip, []).append(time.time())


def _reset(ip: str) -> None:
    _echecs.pop(ip, None)


# Chemins accessibles au rôle « chauffeur » (l'espace constats, uniquement).
_PREFIXES_CHAUFFEUR = (
    "/static", "/etat", "/parametres", "/constats", "/terrain",
    "/terrain-fichier", "/telecharger", "/ouvrir", "/imprimer", "/manifest.json",
)


def _chemin_autorise_chauffeur(methode: str, chemin: str) -> bool:
    """Le chauffeur accède à ses constats, ET peut NAVIGUER (lecture) dans les clients/chantiers
    pour retrouver un devis / un état des lieux, ET ajouter un document à un chantier (scan)."""
    if chemin == "/" or any(chemin.startswith(p) for p in _PREFIXES_CHAUFFEUR):
        return True
    # Navigation en LECTURE : liste et fiches clients, contenu des chantiers, documents.
    if methode == "GET" and (
        chemin == "/clients" or chemin.startswith("/clients/") or chemin.startswith("/chantiers/")
    ):
        return True
    # Ajout d'un document au dossier d'un chantier (POST /chantiers/{id}/documents).
    if methode == "POST" and chemin.startswith("/chantiers/") and chemin.endswith("/documents"):
        return True
    return False


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


def tentative_connexion(identifiant: str, mot_de_passe: str, ip: str) -> tuple[str, str]:
    """Connexion par la page /connexion : anti-force-brute + vérification des identifiants.

    Renvoie (identifiant, rôle) ou lève 429 (IP bloquée) / 401 (identifiants invalides).
    """
    if _bloque(ip):
        logger.warning("AUDIT auth: connexion bloquée (trop de tentatives) depuis %s", ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de tentatives. Réessayez dans quelques minutes.",
            headers={"Retry-After": str(_BLOCAGE_S)},
        )
    resultat = _authentifier(identifiant, mot_de_passe)
    if resultat:
        _reset(ip)
        return resultat
    _echec(ip)
    logger.warning("AUDIT auth: échec de connexion depuis %s", ip)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Identifiant ou mot de passe incorrect."
    )


# Chemins servis SANS authentification : la page de connexion, la déconnexion (doit toujours
# fonctionner, y compris pour un chauffeur cloisonné), le manifeste PWA et le service worker.
_CHEMINS_PUBLICS = ("/connexion", "/deconnexion", "/manifest.json", "/sw.js")


def _valide_et_gate_chauffeur(request: Request, identifiant: str, role: str) -> None:
    request.state.utilisateur, request.state.role = identifiant, role
    # Rôle « chauffeur » : constats + navigation lecture clients/chantiers + ajout de documents.
    if role == "chauffeur" and not _chemin_autorise_chauffeur(request.method, request.url.path):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé — votre compte chauffeur ne couvre que les constats.",
        )


def exiger_auth(
    request: Request, credentials: HTTPBasicCredentials | None = Depends(_basic)
) -> None:
    """Dépendance globale : cookie de session OU Basic ; anti-brute-force ; page /connexion."""
    if request.url.path in _CHEMINS_PUBLICS:
        request.state.utilisateur, request.state.role = "public", "public"
        return
    if not auth_configuree():
        request.state.utilisateur = "poste-local"
        request.state.role = "admin"
        return

    # 1) Session par cookie (page de connexion) — le chemin normal des navigateurs.
    jeton = request.cookies.get(COOKIE_SESSION)
    if jeton:
        resultat = valider_session(jeton)
        if resultat:
            _valide_et_gate_chauffeur(request, *resultat)
            return

    ip = ip_client(request)
    if _bloque(ip):
        logger.warning("AUDIT auth: accès bloqué (trop de tentatives) depuis %s", ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de tentatives. Réessayez dans quelques minutes.",
            headers={"Retry-After": str(_BLOCAGE_S)},
        )

    # 2) Auth Basic (compatibilité scripts/API + secours).
    if credentials is not None:
        resultat = _authentifier(credentials.username, credentials.password)
        if resultat:
            _reset(ip)
            _valide_et_gate_chauffeur(request, *resultat)
            return
        _echec(ip)
        # On ne journalise PAS l'identifiant saisi : un mot de passe tapé par erreur dans le champ
        # « utilisateur » finirait en clair dans les logs (minimisation, art. 5 RGPD).
        logger.warning("AUDIT auth: échec d'authentification depuis %s", ip)

    # 3) Rien de valide : le navigateur qui demande une PAGE part sur /connexion ;
    #    les appels d'API reçoivent un 401 classique.
    if request.method == "GET" and request.url.path == "/":
        raise HTTPException(
            status_code=status.HTTP_302_FOUND, headers={"Location": "/connexion"}
        )
    # Pas d'en-tête WWW-Authenticate : sinon les navigateurs rouvrent leur boîte de dialogue
    # grise par-dessus notre page de connexion. L'interface redirige elle-même sur 401.
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentification requise."
    )
