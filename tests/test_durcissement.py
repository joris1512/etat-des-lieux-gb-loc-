"""Tests du durcissement issu de la revue (sécurité + robustesse + correctness)."""

import asyncio
import io
import json
import zipfile

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from openpyxl import Workbook
from starlette.responses import PlainTextResponse

from app import main, modeles, remplissage
from app.assemblage import construire_plan
from app.config import FIXTURES_DIR, get_reglages
from app.correspondance import charger_correspondances
from app.extraction import charger_fixture
from app.generation import generer
from app.models import ArticleDevis, EnteteDevis, EtatDesLieux, ExtractionDevis

ENTETE = EnteteDevis(
    client="X", titre_chantier="Y", adresse="Z", code_postal="00000", numero_offre="TEST"
)


# ---------------------------------------------------------------- #2 : auth non-ASCII -> 401
@pytest.fixture
def client_auth(monkeypatch):
    monkeypatch.setenv("GB_PASSWORD", "secret")
    get_reglages.cache_clear()
    yield TestClient(main.app)
    get_reglages.cache_clear()


def test_identifiants_non_ascii_donnent_401(client_auth):
    assert client_auth.get("/modeles", auth=("gb", "café-€")).status_code == 401
    assert client_auth.get("/modeles", auth=("utilisé", "secret")).status_code == 401


# ---------------------------------------------------------------- #17 : middleware taille requête
def _appeler_middleware(content_length: str):
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/generer",
        "headers": [(b"content-length", content_length.encode())],
    }
    from starlette.requests import Request

    request = Request(scope)

    async def call_next(_req):
        return PlainTextResponse("ok")

    return asyncio.run(main.limiter_taille_requete(request, call_next))


def test_requete_trop_volumineuse_413():
    assert _appeler_middleware(str(26 * 1024 * 1024)).status_code == 413


def test_requete_raisonnable_passe():
    assert _appeler_middleware("2048").status_code == 200


# ---------------------------------------------------------------- #8 : zip_nom assaini
def test_zip_nom_assaini_contre_traversal():
    base = json.loads((FIXTURES_DIR / "eiffage_extraction.json").read_text(encoding="utf-8"))
    base["entete"]["numero_offre"] = "GB\\..\\evil/123"
    f = FIXTURES_DIR / "_test_malicious.json"
    f.write_text(json.dumps(base), encoding="utf-8")
    try:
        rapport, job_dir = generer(None, utiliser_fixture=True, fixture_nom="_test_malicious.json")
        assert rapport.zip_nom and "/" not in rapport.zip_nom and "\\" not in rapport.zip_nom
        cible = (job_dir / rapport.zip_nom).resolve()
        assert cible.parent == job_dir.resolve()
        assert cible.exists()
    finally:
        f.unlink(missing_ok=True)


# ---------------------------------------------------------------- #11 : bloc vide ne fusionne pas
def test_bloc_vide_ne_fusionne_pas():
    arts = [
        ArticleDevis(texte_ligne="BUNGALOW 15m2 BATISO", bloc="", est_bungalow=True),
        ArticleDevis(texte_ligne="BUNGALOW 15m2 BATISO", bloc="   ", est_bungalow=True),
    ]
    plan = construire_plan(ExtractionDevis(entete=ENTETE, articles=arts))
    assert [e.type_etat for e in plan.etats] == ["individuel", "individuel"]


# ---------------------------------------------------------------- #12 : divergence type signalée
def test_divergence_type_signalee():
    # La table classe « BUNGALOW 15m2 BATISO » en bungalow ; le LLM dit non-bungalow.
    arts = [ArticleDevis(texte_ligne="BUNGALOW 15m2 BATISO", bloc="X", est_bungalow=False)]
    plan = construire_plan(ExtractionDevis(entete=ENTETE, articles=arts))
    assert any("Type incertain" in a for a in plan.avertissements)


# ---------------------------------------------------------------- #13 : départage déterministe
def test_tiebreak_motifs_meme_longueur(tmp_path):
    csv = tmp_path / "c.csv"
    csv.write_text(
        "pattern,modele,categorie,est_bungalow\nBBBB,b.xlsx,x,true\nAAAA,a.xlsx,x,true\n",
        encoding="utf-8",
    )
    charger_correspondances.cache_clear()
    try:
        entrees = charger_correspondances(csv)
        assert [e.pattern_norm for e in entrees] == ["AAAA", "BBBB"]
    finally:
        charger_correspondances.cache_clear()


# ---------------------------------------------------------------- #16 : zip-bomb / non-zip rejetés
def test_modele_non_zip_rejete():
    with pytest.raises(ValueError):
        modeles.enregistrer_modele("x.xlsx", b"pas un zip du tout")


def test_modele_ratio_compression_suspect_rejete():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("x", b"\0" * (2 * 1024 * 1024))  # 2 Mo de zéros -> compressé minuscule
    with pytest.raises(ValueError):
        modeles.enregistrer_modele("bomb.xlsx", buf.getvalue())


# ---------------------------------------------------------------- #18 : feuille absente -> ValueError
def test_feuille_absente_message_clair(monkeypatch, tmp_path):
    wb = Workbook()
    wb.active.title = "AutreFeuille"
    chemin = tmp_path / "m.xlsx"
    wb.save(chemin)
    monkeypatch.setattr(
        remplissage, "_cfg_modele", lambda m: {"feuille": "Inexistante", "entete": {}, "mobilier": {}}
    )
    etat = EtatDesLieux(modele="m.xlsx", type_etat="individuel", texte_ligne="x", nom_fichier="o.xlsx")
    with pytest.raises(ValueError):
        remplissage.remplir_etat(chemin, tmp_path / "o.xlsx", ENTETE, etat)


# ---------------------------------------------------------------- #20 : fixture introuvable -> ValueError
def test_fixture_introuvable_message_clair():
    with pytest.raises(ValueError):
        charger_fixture("nexiste_vraiment_pas.json")


# ---------------------------------------------------------------- #9 : résolution de fichier durcie
def test_fichier_du_job_rejette_les_chemins_dangereux(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "SORTIES_DIR", tmp_path)
    job = tmp_path / "abc"
    job.mkdir()
    (job / "ok.xlsx").write_text("x")

    assert main._fichier_du_job("abc", "ok.xlsx").name == "ok.xlsx"
    for mauvais_job in ["..", ".", "a/b", "a\\b", ""]:
        with pytest.raises(HTTPException):
            main._fichier_du_job(mauvais_job, "ok.xlsx")
    for mauvais_nom in ["../x", "a/b", "a\\b"]:
        with pytest.raises(HTTPException):
            main._fichier_du_job("abc", mauvais_nom)
