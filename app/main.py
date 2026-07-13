"""Application FastAPI : upload du devis, génération, téléchargement (individuel + ZIP)."""

from __future__ import annotations

import logging
import os
import shutil
from collections import Counter
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import db, import_csv, terrain
from app.assemblage import construire_plan, resoudre_modele
from app.config import (
    DONNEES_DIR,
    HTML_DIR,
    RACINE,
    RUNTIME_DIR,
    SORTIES_DIR,
    STATIC_DIR,
    VERSION,
    get_reglages,
)
from app.sauvegarde import sauvegarder_quotidienne
from app.correspondance import (
    ajouter_ou_modifier_regle,
    est_prestation,
    lister_regles,
    supprimer_regle,
    trouver_modele,
)
from app.generation import analyser, generer, generer_depuis_extraction
from app.models import ExtractionDevis
from app.modeles import enregistrer_modele, lister_modeles, modeles_presents, supprimer_modele
from app.purge import purger_anciennes_sorties
from app.securite import (
    auth_configuree,
    exiger_admin,
    exiger_auth,
    hacher,
    utilisateur_courant,
)

logger = logging.getLogger("uvicorn.error")

def migrer_donnees_programme(racine=None, donnees=None, runtime=None) -> None:
    """Récupère les données d'une ANCIENNE installation (stockées dans le dossier programme)
    vers le dossier de données séparé — sans jamais écraser des données déjà migrées."""
    racine, donnees, runtime = racine or RACINE, donnees or DONNEES_DIR, runtime or RUNTIME_DIR
    if donnees == racine:  # mode développement : rien à migrer
        return
    donnees.mkdir(parents=True, exist_ok=True)
    ancien_runtime = racine / "runtime"
    if ancien_runtime.is_dir() and not runtime.exists():
        shutil.copytree(ancien_runtime, runtime)
        logger.info("Données migrées vers le dossier protégé : %s", runtime)
    ancien_env = racine / ".env"
    if ancien_env.is_file() and not (donnees / ".env").exists():
        shutil.copy2(ancien_env, donnees / ".env")
        logger.info("Clé API migrée vers le dossier protégé : %s", donnees)


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    # Migration éventuelle d'une ancienne installation, puis base + purge + sauvegarde du jour.
    try:
        migrer_donnees_programme()
    except Exception as exc:  # noqa: BLE001 — une migration impossible ne doit pas bloquer l'app
        logger.warning("Migration des données impossible : %s", exc)
    db.init_db()
    purger_anciennes_sorties()
    try:
        sauvegarder_quotidienne()
    except Exception as exc:  # noqa: BLE001 — la sauvegarde ne doit jamais bloquer le démarrage
        logger.warning("Sauvegarde quotidienne impossible : %s", exc)
    # État d'authentification visible au démarrage (jamais d'ouverture silencieuse).
    reglages = get_reglages()
    if auth_configuree():
        mode = "hachée" if reglages.mot_de_passe_hash else "clair"
        logger.info("Authentification ACTIVÉE (utilisateur « %s », %s).", reglages.utilisateur, mode)
    else:
        logger.warning(
            "Authentification DÉSACTIVÉE (GB_PASSWORD non défini) — appli OUVERTE sur %s:%s. "
            "Définissez GB_PASSWORD pour la protéger.",
            reglages.host,
            reglages.port,
        )
    yield


app = FastAPI(
    title="GB Location — Pré-remplissage des états des lieux",
    dependencies=[Depends(exiger_auth)],
    lifespan=_lifespan,
)

# Plafond de taille de requête (devis PDF / modèles .xlsx) — borne la mémoire avant bufférisation.
MAX_BODY = 25 * 1024 * 1024  # 25 Mo


@app.middleware("http")
async def limiter_taille_requete(request, call_next):
    longueur = request.headers.get("content-length")
    if longueur and longueur.isdigit() and int(longueur) > MAX_BODY:
        return JSONResponse(
            {"detail": "Requête trop volumineuse (max 25 Mo)."}, status_code=413
        )
    return await call_next(request)


# En-têtes de sécurité (anti-clickjacking, anti-MIME-sniffing, CSP restrictive).
_CSP = (
    "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
    "script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; "
    "base-uri 'self'; form-action 'self'"
)


@app.middleware("http")
async def entetes_securite(request, call_next):
    reponse = await call_next(request)
    reponse.headers.setdefault("X-Content-Type-Options", "nosniff")
    reponse.headers.setdefault("X-Frame-Options", "DENY")
    reponse.headers.setdefault("Referrer-Policy", "no-referrer")
    reponse.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    reponse.headers.setdefault("Content-Security-Policy", _CSP)
    return reponse


# Ressources statiques (logo, favicon) — publiques, pas d'authentification.
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
def accueil() -> HTMLResponse:
    # no-store : la fenêtre de l'application recharge TOUJOURS l'interface à jour
    # (sinon WebView2 peut servir une vieille version en cache après une mise à jour).
    return HTMLResponse(
        (HTML_DIR / "index.html").read_text(encoding="utf-8"),
        headers={"Cache-Control": "no-store, must-revalidate"},
    )


def _reponse_generation(rapport, job_dir: Path) -> dict:
    job_id = job_dir.name
    return {
        "job_id": job_id,
        "numero_offre": rapport.numero_offre,
        "fichiers": [{"nom": n, "url": f"/telecharger/{job_id}/{n}"} for n in rapport.fichiers],
        "zip": (
            {"nom": rapport.zip_nom, "url": f"/telecharger/{job_id}/{rapport.zip_nom}"}
            if rapport.zip_nom
            else None
        ),
        "non_reconnus": rapport.non_reconnus,
        "avertissements": rapport.avertissements,
    }


async def _lire_pdf(fichier: UploadFile | None) -> bytes:
    if fichier is None:
        raise HTTPException(status_code=400, detail="Aucun fichier PDF fourni.")
    if not (fichier.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Le fichier doit être un PDF.")
    data = await fichier.read()
    if not data:
        raise HTTPException(status_code=400, detail="Le PDF est vide.")
    return data


def _apercu(extraction: ExtractionDevis) -> dict:
    """Aperçu du plan (décompte par type + anomalies) sans rien produire."""
    plan = construire_plan(extraction)
    types = Counter(e.type_etat for e in plan.etats)
    return {
        "total": len(plan.etats),
        "assembles": types.get("assemble", 0),
        "individuels": types.get("individuel", 0),
        "sanitaires": types.get("sanitaire", 0),
        "non_reconnus": plan.non_reconnus,
        "avertissements": plan.avertissements,
    }


@app.post("/analyser")
async def analyser_endpoint(
    fichier: UploadFile | None = File(default=None),
    utiliser_fixture: bool = Form(default=False),
):
    """Lit le devis et renvoie l'extraction + un aperçu du plan, SANS générer de fichiers."""
    pdf_bytes = None if utiliser_fixture else await _lire_pdf(fichier)
    try:
        extraction = analyser(pdf_bytes, utiliser_fixture=utiliser_fixture)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Lecture du devis impossible : {exc}") from exc
    # Pré-remplit le modèle déduit de chaque module (que l'utilisateur pourra corriger dans l'UI).
    for art in extraction.articles:
        if art.modele is None:
            res = resoudre_modele(art)
            if res:
                art.modele = res[0]
    return {
        "extraction": extraction.model_dump(),
        "apercu": _apercu(extraction),
        "modeles": modeles_presents(),
    }


@app.post("/generer")
async def generer_endpoint(
    fichier: UploadFile | None = File(default=None),
    utiliser_fixture: bool = Form(default=False),
):
    """Chemin direct : lit le devis et génère immédiatement (sans étape de révision)."""
    pdf_bytes = None if utiliser_fixture else await _lire_pdf(fichier)
    try:
        rapport, job_dir = generer(pdf_bytes, utiliser_fixture=utiliser_fixture)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Échec de la génération : {exc}") from exc
    return _reponse_generation(rapport, job_dir)


@app.post("/generer-revise")
def generer_revise_endpoint(extraction: ExtractionDevis):
    """Génère à partir d'une extraction révisée par l'utilisateur (en-tête + modules corrigés)."""
    try:
        rapport, job_dir = generer_depuis_extraction(extraction)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Échec de la génération : {exc}") from exc
    # Auto-apprentissage : si l'utilisateur a choisi un modèle pour une ligne que la table ne
    # reconnaît pas, on mémorise la règle (ligne exacte -> modèle). Modifiable/supprimable
    # ensuite dans l'onglet Modèles ; n'écrase jamais une règle existante.
    for art in extraction.articles:
        if art.modele and trouver_modele(art.texte_ligne) is None and not est_prestation(art.texte_ligne):
            try:
                ajouter_ou_modifier_regle(
                    art.texte_ligne, art.modele,
                    categorie="apprise",
                    est_bungalow="bungalow" in art.modele.lower(),
                )
                rapport.avertissements.append(
                    f"Règle apprise : « {art.texte_ligne} » → {art.modele} (modifiable dans Modèles)."
                )
                logger.info("AUDIT règle apprise : %s -> %s", art.texte_ligne, art.modele)
            except ValueError:
                pass
    return _reponse_generation(rapport, job_dir)


@app.get("/etat")
def etat(request: Request) -> dict:
    """État léger pour l'UI : authentification, identité connectée, rôle, version."""
    return {
        "auth": auth_configuree(),
        "utilisateur": utilisateur_courant(request),
        "role": getattr(request.state, "role", "admin"),
        "version": VERSION,
    }


# --------------------------------------------------------------------------- #
# Paramètres (marque blanche : nom de société + logo) — modification admin
# --------------------------------------------------------------------------- #
_LOGO_CLIENT = "logo_client.png"


@app.get("/parametres")
def parametres_lire() -> dict:
    """Personnalisation affichée par l'UI (nom de société, logo)."""
    logo = f"/static/{_LOGO_CLIENT}" if (STATIC_DIR / _LOGO_CLIENT).exists() else "/static/logo.png"
    return {"societe": db.lire_parametre("societe", "") or "", "logo": logo}


@app.post("/parametres")
async def parametres_ecrire(request: Request, corps: dict) -> dict:
    exiger_admin(request)
    societe = (corps.get("societe") or "").strip()[:80]
    db.ecrire_parametre("societe", societe)
    logger.info("AUDIT paramètres : société = « %s » par %s", societe, utilisateur_courant(request))
    return parametres_lire()


@app.post("/parametres/logo")
async def parametres_logo(request: Request, fichier: UploadFile = File(...)) -> dict:
    exiger_admin(request)
    contenu = await fichier.read()
    if not contenu or len(contenu) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image requise (2 Mo max).")
    # Signatures de fichier : PNG ou JPEG uniquement (pas de SVG ni de HTML déguisé).
    est_png = contenu.startswith(b"\x89PNG\r\n\x1a\n")
    est_jpeg = contenu.startswith(b"\xff\xd8\xff")
    if not (est_png or est_jpeg):
        raise HTTPException(status_code=400, detail="Format accepté : PNG ou JPEG.")
    (STATIC_DIR / _LOGO_CLIENT).write_bytes(contenu)
    logger.info("AUDIT paramètres : logo remplacé par %s", utilisateur_courant(request))
    return parametres_lire()


@app.delete("/parametres/logo")
def parametres_logo_defaut(request: Request) -> dict:
    exiger_admin(request)
    (STATIC_DIR / _LOGO_CLIENT).unlink(missing_ok=True)
    logger.info("AUDIT paramètres : retour au logo par défaut par %s", utilisateur_courant(request))
    return parametres_lire()


# --------------------------------------------------------------------------- #
# Comptes utilisateurs (multi-postes) — gestion réservée aux administrateurs
# --------------------------------------------------------------------------- #
@app.get("/utilisateurs")
def utilisateurs_lister(request: Request) -> dict:
    exiger_admin(request)
    return {"utilisateurs": db.lister_utilisateurs()}


@app.post("/utilisateurs")
async def utilisateurs_creer(request: Request, corps: dict) -> dict:
    exiger_admin(request)
    identifiant = (corps.get("identifiant") or "").strip()
    nom = (corps.get("nom_affiche") or "").strip() or identifiant
    mdp = corps.get("mot_de_passe") or ""
    role = (corps.get("role") or "utilisateur").strip()
    if not identifiant or len(mdp) < 8:
        raise HTTPException(
            status_code=400, detail="Identifiant requis et mot de passe d'au moins 8 caractères."
        )
    try:
        db.creer_utilisateur(identifiant, nom, hacher(mdp), role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    logger.info("AUDIT compte créé : %s (%s) par %s", identifiant, role, utilisateur_courant(request))
    return {"utilisateurs": db.lister_utilisateurs()}


@app.post("/utilisateurs/{uid}/mot-de-passe")
async def utilisateurs_mdp(uid: int, request: Request, corps: dict) -> dict:
    exiger_admin(request)
    mdp = corps.get("mot_de_passe") or ""
    if len(mdp) < 8:
        raise HTTPException(status_code=400, detail="Mot de passe d'au moins 8 caractères.")
    try:
        db.modifier_utilisateur(uid, hash_=hacher(mdp))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    logger.info("AUDIT mot de passe réinitialisé pour le compte n° %s par %s", uid, utilisateur_courant(request))
    return {"ok": True}


@app.post("/utilisateurs/{uid}/actif")
async def utilisateurs_actif(uid: int, request: Request, corps: dict) -> dict:
    exiger_admin(request)
    try:
        db.modifier_utilisateur(uid, actif=bool(corps.get("actif")))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    logger.info("AUDIT compte n° %s actif=%s par %s", uid, bool(corps.get("actif")), utilisateur_courant(request))
    return {"utilisateurs": db.lister_utilisateurs()}


@app.get("/stats")
def stats_endpoint() -> dict:
    """Données du tableau de bord : agrégats de la base + état des modèles."""
    s = db.dashboard()
    mod = lister_modeles()
    total_mod = len(mod["attendus"])
    return {
        **s,
        "modeles_presents": total_mod - mod["manquants"],
        "modeles_total": total_mod,
        "modeles_manquants": mod["manquants"],
    }


@app.get("/historique")
def historique_endpoint(q: str | None = None) -> dict:
    """Liste des générations passées (recherche par client / offre / chantier)."""
    return {"generations": db.lister_historique(q)}


@app.get("/clients")
def clients_endpoint() -> dict:
    """Annuaire des clients connus de la base (agrégats)."""
    return {"clients": db.lister_clients()}


@app.post("/clients/importer-csv")
async def importer_csv_endpoint(fichier: UploadFile = File(...)) -> dict:
    """Importe une base clients depuis un CSV (export CRM / tableur)."""
    if not (fichier.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Le fichier doit être un .csv.")
    contenu = await fichier.read()
    if not contenu:
        raise HTTPException(status_code=400, detail="Le fichier est vide.")
    try:
        lignes = import_csv.parser(contenu)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"CSV illisible : {exc}") from exc
    res = {"nouveaux": 0, "enrichis": 0, "ignores": 0}
    cle = {"nouveau": "nouveaux", "enrichi": "enrichis", "ignore": "ignores"}
    for ligne in lignes:
        res[cle[db.importer_client(**ligne)]] += 1
    logger.info("AUDIT import CSV : %s ligne(s) → %s", len(lignes), res)
    return {"total": len(lignes), **res, "clients": db.lister_clients()}


@app.get("/clients/{client_id}")
def client_detail_endpoint(client_id: int) -> dict:
    """Fiche client : coordonnées, interlocuteurs, chantiers (triés par nom), devis."""
    c = db.lire_client(client_id)
    if not c:
        raise HTTPException(status_code=404, detail="Client introuvable.")
    return c


@app.patch("/clients/{client_id}")
async def client_modifier_endpoint(client_id: int, corps: dict, request: Request) -> dict:
    """Édition de la fiche client : coordonnées, n° client, notes libres."""
    try:
        ok = db.modifier_client(client_id, corps)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not ok:
        raise HTTPException(status_code=404, detail="Client introuvable.")
    logger.info("AUDIT fiche client n° %s modifiée par %s", client_id, utilisateur_courant(request))
    return db.lire_client(client_id)


@app.post("/clients/{client_id}/interlocuteurs")
async def interlocuteur_ajouter_endpoint(client_id: int, corps: dict) -> dict:
    try:
        db.ajouter_interlocuteur(client_id, corps.get("nom") or "")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return db.lire_client(client_id)


@app.delete("/clients/{client_id}/interlocuteurs")
def interlocuteur_supprimer_endpoint(client_id: int, nom: str) -> dict:
    db.supprimer_interlocuteur(client_id, nom)
    c = db.lire_client(client_id)
    if not c:
        raise HTTPException(status_code=404, detail="Client introuvable.")
    return c


@app.delete("/clients/{client_id}")
def client_supprimer_endpoint(client_id: int, request: Request) -> dict:
    """Efface un client et toutes ses données (RGPD — droit à l'effacement), fichiers compris."""
    jobs = db.supprimer_client(client_id)
    if jobs is None:
        raise HTTPException(status_code=404, detail="Client introuvable.")
    # Purge des dossiers de sortie liés (les fichiers portent le nom du client).
    base = SORTIES_DIR.resolve()
    purges = 0
    for job_id in jobs:
        cible = (SORTIES_DIR / job_id).resolve()
        if cible.parent == base and cible.exists():  # garde anti-évasion de chemin
            shutil.rmtree(cible, ignore_errors=True)
            purges += 1
    # Journal d'audit volontairement anonyme (pas de donnée nominative dans les logs).
    logger.info(
        "AUDIT effacement RGPD : fiche client n° %s (%s dossier(s) purgé(s)) par %s.",
        client_id, purges, utilisateur_courant(request),
    )
    return {"supprime": True, "dossiers_purges": purges}


@app.get("/chantiers/{chantier_id}")
def chantier_detail_endpoint(chantier_id: int) -> dict:
    """Contenu d'un chantier : devis, états des lieux (documents), historique."""
    ch = db.lire_chantier(chantier_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Chantier introuvable.")
    return ch


@app.get("/stats/avancees")
def stats_avancees_endpoint() -> dict:
    """Séries pour la page Statistiques (par jour, top clients, répartition)."""
    return db.stats_avancees()


@app.get("/modeles")
def modeles_lister() -> dict:
    """État des modèles Excel (attendus présents/manquants + fichiers supplémentaires)."""
    return lister_modeles()


@app.get("/correspondances")
def correspondances_lister() -> dict:
    """Règles de reconnaissance « texte du devis → modèle » + modèles disponibles."""
    return {"regles": lister_regles(), "modeles": modeles_presents()}


@app.post("/correspondances")
async def correspondances_enregistrer(regle: dict, request: Request) -> dict:
    """Ajoute une règle ou remplace celle du même mot déclencheur."""
    pattern = (regle.get("pattern") or "").strip()
    modele = (regle.get("modele") or "").strip()
    if not pattern or not modele:
        raise HTTPException(status_code=400, detail="Mot déclencheur et modèle sont requis.")
    try:
        ajouter_ou_modifier_regle(
            pattern, modele, regle.get("categorie") or "", bool(regle.get("est_bungalow"))
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    logger.info("AUDIT règle enregistrée : %s -> %s par %s", pattern, modele, utilisateur_courant(request))
    return {"regles": lister_regles(), "modeles": modeles_presents()}


@app.delete("/correspondances")
def correspondances_supprimer(pattern: str, request: Request) -> dict:
    """Supprime la règle du mot déclencheur donné."""
    supprimer_regle(pattern)
    logger.info("AUDIT règle supprimée : %s par %s", pattern, utilisateur_courant(request))
    return {"regles": lister_regles(), "modeles": modeles_presents()}


@app.post("/modeles")
async def modeles_televerser(fichiers: list[UploadFile] = File(...)) -> dict:
    """Téléverse un ou plusieurs modèles .xlsx (remplace s'il existe déjà)."""
    resultats = []
    for f in fichiers:
        try:
            contenu = await f.read()
            nom = enregistrer_modele(f.filename or "", contenu)
            resultats.append({"nom": nom, "ok": True})
        except Exception as exc:  # noqa: BLE001
            resultats.append({"nom": f.filename, "ok": False, "erreur": str(exc)})
    return {"resultats": resultats, "modeles": lister_modeles()}


@app.delete("/modeles/{nom}")
def modeles_supprimer(nom: str, request: Request) -> dict:
    """Supprime un modèle de la bibliothèque."""
    try:
        supprimer_modele(nom)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    logger.info("AUDIT modèle supprimé : %s par %s", nom, utilisateur_courant(request))
    return lister_modeles()


def _fichier_du_job(job_id: str, nom: str) -> Path:
    """Résout un fichier de sortie en empêchant toute évasion de chemin.

    `job_id` doit être un dossier enfant direct de SORTIES_DIR, et `nom` un simple nom de
    fichier (aucun séparateur, ni `.`/`..`). Comparaisons de parents strictes (pas `in parents`).
    """
    base_dir = SORTIES_DIR.resolve()
    if not job_id or job_id in {".", ".."} or "/" in job_id or "\\" in job_id:
        raise HTTPException(status_code=400, detail="Job invalide.")
    job_dir = (SORTIES_DIR / job_id).resolve()
    if job_dir.parent != base_dir:
        raise HTTPException(status_code=400, detail="Job invalide.")

    base_nom = Path(nom.replace("\\", "/")).name
    if not base_nom or base_nom != nom:
        raise HTTPException(status_code=400, detail="Chemin invalide.")
    cible = (job_dir / base_nom).resolve()
    if cible.parent != job_dir:
        raise HTTPException(status_code=400, detail="Chemin invalide.")
    if not cible.exists():
        raise HTTPException(status_code=404, detail="Fichier introuvable.")
    return cible


# --------------------------------------------------------------------------- #
# Mode chauffeur (terrain) : constat début/fin, photos, signature, PDF, partage
# --------------------------------------------------------------------------- #
def _contexte_constat(job_id: str, nom: str):
    document = _fichier_du_job(job_id, nom)
    if document.suffix.lower() != ".xlsx":
        raise HTTPException(status_code=400, detail="Constat disponible sur les documents Excel.")
    dossier = terrain.dossier_constat(document.parent, nom)
    return document, dossier


@app.get("/terrain/{job_id}/{nom}")
def constat_lire(job_id: str, nom: str) -> dict:
    document, dossier = _contexte_constat(job_id, nom)
    return terrain.charger_constat(document, None, dossier)


@app.post("/terrain/{job_id}/{nom}")
async def constat_enregistrer(job_id: str, nom: str, corps: dict) -> dict:
    document, dossier = _contexte_constat(job_id, nom)
    lignes = corps.get("lignes") or []
    try:
        terrain.enregistrer_constat(document, None, lignes, dossier)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"Enregistrement impossible : {exc}") from exc
    return terrain.charger_constat(document, None, dossier)


@app.post("/terrain/{job_id}/{nom}/photo")
async def constat_photo(job_id: str, nom: str, fichier: UploadFile = File(...)) -> dict:
    document, dossier = _contexte_constat(job_id, nom)
    contenu = await fichier.read()
    if not contenu or len(contenu) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Photo requise (8 Mo max).")
    try:
        terrain.ajouter_photo(dossier, contenu)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return terrain.charger_constat(document, None, dossier)


@app.post("/terrain/{job_id}/{nom}/signature")
async def constat_signature(job_id: str, nom: str, corps: dict) -> dict:
    document, dossier = _contexte_constat(job_id, nom)
    image = corps.get("image") or ""
    prefixe = "data:image/png;base64,"
    if not image.startswith(prefixe):
        raise HTTPException(status_code=400, detail="Signature invalide.")
    import base64

    try:
        png = base64.b64decode(image[len(prefixe):])
        terrain.enregistrer_signature(dossier, png, corps.get("signataire") or "")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Signature illisible : {exc}") from exc
    logger.info("AUDIT constat signé : %s (%s)", nom, job_id)
    return terrain.charger_constat(document, None, dossier)


@app.post("/terrain/{job_id}/{nom}/pdf")
def constat_pdf(job_id: str, nom: str) -> dict:
    document, dossier = _contexte_constat(job_id, nom)
    infos = db.infos_job(job_id)
    sous_titre = " · ".join(x for x in (infos.get("client"), infos.get("chantier"), infos.get("offre")) if x)
    societe = db.lire_parametre("societe", "") or ""
    terrain.generer_pdf(dossier, titre=Path(nom).stem, sous_titre=sous_titre, societe=societe)
    return terrain.charger_constat(document, None, dossier)


@app.get("/terrain-fichier/{job_id}/{nom}/{piece}")
def constat_piece(job_id: str, nom: str, piece: str) -> FileResponse:
    """Sert une pièce du constat (photo / PDF) avec les mêmes gardes que les documents."""
    _document, dossier = _contexte_constat(job_id, nom)
    base_piece = Path(piece.replace("\\", "/")).name
    if not base_piece or base_piece != piece:
        raise HTTPException(status_code=400, detail="Chemin invalide.")
    cible = (dossier / base_piece).resolve()
    if cible.parent != dossier.resolve() or not cible.exists():
        raise HTTPException(status_code=404, detail="Pièce introuvable.")
    media = "application/pdf" if cible.suffix == ".pdf" else "image/png" if cible.suffix == ".png" else "image/jpeg"
    return FileResponse(cible, filename=base_piece, media_type=media)


@app.post("/terrain/{job_id}/{nom}/partager")
def constat_partager(job_id: str, nom: str, request: Request) -> dict:
    """Ouvre un e-mail prérempli avec le PDF de constat en pièce jointe (poste local)."""
    _exiger_poste_local(request)
    document, dossier = _contexte_constat(job_id, nom)
    pdf = dossier / "constat.pdf"
    if not pdf.exists():
        infos = db.infos_job(job_id)
        sous_titre = " · ".join(x for x in (infos.get("client"), infos.get("chantier")) if x)
        terrain.generer_pdf(dossier, titre=Path(nom).stem, sous_titre=sous_titre,
                            societe=db.lire_parametre("societe", "") or "")
    infos = db.infos_job(job_id)
    sujet = f"État des lieux — {infos.get('chantier') or Path(nom).stem}"
    script = (
        "$o = New-Object -ComObject Outlook.Application; $m = $o.CreateItem(0); "
        f"$m.Subject = '{sujet.replace(chr(39), ' ')}'; "
        "$m.Body = 'Bonjour,`r`n`r`nVeuillez trouver ci-joint le constat d''état des lieux.`r`n'; "
        f"$m.Attachments.Add('{pdf}') | Out-Null; $m.Display()"
    )
    import subprocess

    essai = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True, timeout=30, check=False,
    )
    if essai.returncode != 0:  # pas d'Outlook : on ouvre le dossier du constat
        os.startfile(str(dossier))  # noqa: S606
        return {"ok": True, "mode": "dossier"}
    return {"ok": True, "mode": "outlook"}


@app.get("/telecharger/{job_id}/{nom}")
def telecharger(job_id: str, nom: str) -> FileResponse:
    cible = _fichier_du_job(job_id, nom)
    media = (
        "application/zip"
        if cible.suffix == ".zip"
        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    return FileResponse(cible, filename=nom, media_type=media)


def _exiger_poste_local(request: Request) -> None:
    """N'autorise l'ouverture directe que depuis CE poste (sinon Excel s'ouvrirait sur le serveur)."""
    hote = (request.client.host if request.client else "") or ""
    if hote not in ("127.0.0.1", "::1", "localhost"):
        raise HTTPException(
            status_code=403,
            detail="Ouverture directe disponible uniquement sur le poste local — utilisez Télécharger.",
        )


@app.post("/ouvrir/{job_id}/{nom}")
def ouvrir_fichier(job_id: str, nom: str, request: Request) -> dict:
    """Ouvre le document directement dans Excel (application de bureau, poste local uniquement)."""
    _exiger_poste_local(request)
    cible = _fichier_du_job(job_id, nom)
    os.startfile(str(cible))  # noqa: S606 — chemin validé par _fichier_du_job
    return {"ok": True}


@app.post("/imprimer/{job_id}/{nom}")
def imprimer_fichier(job_id: str, nom: str, request: Request) -> dict:
    """Imprime le document sur l'imprimante par défaut (verbe d'impression Windows, poste local)."""
    _exiger_poste_local(request)
    cible = _fichier_du_job(job_id, nom)
    try:
        os.startfile(str(cible), "print")  # noqa: S606 — chemin validé par _fichier_du_job
    except OSError as exc:
        raise HTTPException(
            status_code=400,
            detail="Impression directe indisponible sur ce poste — ouvrez le document et imprimez depuis Excel.",
        ) from exc
    logger.info("AUDIT impression : %s (%s) par %s", nom, job_id, utilisateur_courant(request))
    return {"ok": True}


@app.post("/ouvrir-dossier/{job_id}")
def ouvrir_dossier(job_id: str, request: Request) -> dict:
    """Ouvre le dossier des documents générés dans l'explorateur (poste local uniquement)."""
    _exiger_poste_local(request)
    base = SORTIES_DIR.resolve()
    dossier = (SORTIES_DIR / job_id).resolve()
    if not job_id or dossier.parent != base or not dossier.is_dir():
        raise HTTPException(status_code=404, detail="Dossier introuvable.")
    os.startfile(str(dossier))  # noqa: S606
    return {"ok": True}
