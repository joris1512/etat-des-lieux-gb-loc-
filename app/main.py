"""Application FastAPI : upload du devis, génération, téléchargement (individuel + ZIP)."""

from __future__ import annotations

import logging
from collections import Counter
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import db, import_csv
from app.assemblage import construire_plan
from app.config import HTML_DIR, SORTIES_DIR, STATIC_DIR, get_reglages
from app.generation import analyser, generer, generer_depuis_extraction
from app.models import ExtractionDevis
from app.modeles import enregistrer_modele, lister_modeles, supprimer_modele
from app.purge import purger_anciennes_sorties
from app.securite import auth_configuree, exiger_auth

logger = logging.getLogger("uvicorn.error")

@asynccontextmanager
async def _lifespan(_app: FastAPI):
    # Base de connaissance + purge des anciennes sorties au démarrage.
    db.init_db()
    purger_anciennes_sorties()
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
def accueil() -> str:
    return (HTML_DIR / "index.html").read_text(encoding="utf-8")


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
    return {"extraction": extraction.model_dump(), "apercu": _apercu(extraction)}


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
    return _reponse_generation(rapport, job_dir)


@app.get("/etat")
def etat() -> dict:
    """État léger pour l'UI : authentification active et identifiant courant."""
    reglages = get_reglages()
    return {"auth": auth_configuree(), "utilisateur": reglages.utilisateur}


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
def modeles_supprimer(nom: str) -> dict:
    """Supprime un modèle de la bibliothèque."""
    try:
        supprimer_modele(nom)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    logger.info("AUDIT modèle supprimé : %s", nom)
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


@app.get("/telecharger/{job_id}/{nom}")
def telecharger(job_id: str, nom: str) -> FileResponse:
    cible = _fichier_du_job(job_id, nom)
    media = (
        "application/zip"
        if cible.suffix == ".zip"
        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    return FileResponse(cible, filename=nom, media_type=media)
