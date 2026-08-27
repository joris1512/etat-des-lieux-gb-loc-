"""V2 — déduction des variantes de bungalow, assemblé kit, auto-apprentissage, sauvegardes."""

import zipfile

from fastapi.testclient import TestClient

from app import db, sauvegarde
from app.assemblage import _variante_bungalow, construire_plan
from app.correspondance import charger_correspondances, trouver_modele
from app.main import app
from app.models import ArticleDevis, EnteteDevis, ExtractionDevis, MobilierItem

ENTETE = EnteteDevis(client="X", titre_chantier="Y", adresse="", code_postal="")


def _bung(texte="BUNGALOW 15M2", bloc=None, mobilier=None, assemble=False):
    return ArticleDevis(
        texte_ligne=texte, bloc=bloc, est_bungalow=True, mobilier=mobilier or [], assemble=assemble
    )


FRIGO = MobilierItem(designation="ACCESSOIRE REFRIGERATEUR", quantite=1)
TABLE = MobilierItem(designation="TABLE MODULAIRE RECT. 160X80", quantite=2)


def test_variantes_taille():
    assert _variante_bungalow(_bung("BUNGALOW 8M2 VIDE")) == "bungalow_8m2_vide.xlsx"
    assert _variante_bungalow(_bung("BUNGALOW 8M2 AVEC COIN SANITAIRE")) == "bungalow_8m2_sanitaire.xlsx"
    assert _variante_bungalow(_bung("BUNGALOW 20M2")) == "bungalow_20m2_vide.xlsx"


def test_variantes_mots_cles():
    assert _variante_bungalow(_bung("BUNGALOW PETITE ENFANCE")) == "bungalow_petite_enfance.xlsx"
    assert _variante_bungalow(_bung("BUNGALOW 15M2 COIN SANITAIRE")) == "bungalow_coin_sanitaire.xlsx"
    assert (
        _variante_bungalow(_bung("BUNGALOW 15M2 COIN SANITAIRE", mobilier=[FRIGO]))
        == "bungalow_coin_sanitaire_kitchenette.xlsx"
    )


def test_variante_refectoire_et_mobilier():
    # Réfectoire avec équipement -> modèle réfectoire-kitchenette.
    assert (
        _variante_bungalow(_bung(bloc="REFECTOIRE", mobilier=[FRIGO]))
        == "bungalow_refectoire_kitchenette.xlsx"
    )
    # Mobilier de bureau simple -> modèle avec mobilier ; rien -> vide.
    assert _variante_bungalow(_bung(bloc="BUREAU", mobilier=[TABLE])) == "bungalow_mobilier.xlsx"
    assert _variante_bungalow(_bung(bloc="BUREAU")) == "bungalow_vide.xlsx"


def test_assemble_kit_si_kitchenette():
    arts = [
        _bung(bloc="REFECTOIRE", assemble=True),
        _bung(bloc="REFECTOIRE", mobilier=[FRIGO], assemble=True),
        _bung(bloc="BUREAUX", assemble=True),
        _bung(bloc="BUREAUX", mobilier=[TABLE], assemble=True),
    ]
    plan = construire_plan(ExtractionDevis(entete=ENTETE, articles=arts))
    assembles = {e.bloc: e.modele for e in plan.etats if e.type_etat == "assemble"}
    assert assembles["REFECTOIRE"] == "bungalow_assemble_kit.xlsx"
    assert assembles["BUREAUX"] == "bungalow_assemble.xlsx"


def test_generer_revise_apprend_les_corrections(tmp_path, monkeypatch):
    """Une ligne inconnue + modèle choisi à la main -> règle mémorisée automatiquement."""
    import shutil

    import app.correspondance as corr

    copie = tmp_path / "correspondances.csv"
    shutil.copy(corr.CORRESPONDANCES_CSV, copie)  # table isolée : la vraie n'est pas modifiée
    monkeypatch.setattr(corr, "CORRESPONDANCES_CSV", copie)
    charger_correspondances.cache_clear()
    try:
        ligne = "MODULE ATYPIQUE JAMAIS VU 999"
        assert trouver_modele(ligne) is None
        payload = {
            "entete": {"client": "ACME", "titre_chantier": "", "adresse": "", "code_postal": ""},
            "articles": [
                {"texte_ligne": ligne, "bloc": None, "est_bungalow": False,
                 "quantite": 1, "mobilier": [], "modele": "wc_3.xlsx"}
            ],
        }
        r = TestClient(app).post("/generer-revise", json=payload)
        assert r.status_code == 200
        entree = trouver_modele(ligne)
        assert entree is not None and entree.modele == "wc_3.xlsx"
        assert any("Règle apprise" in a for a in r.json()["avertissements"])
    finally:
        charger_correspondances.cache_clear()


def test_ouvrir_refuse_hors_poste_local():
    # Le TestClient se présente comme « testclient » (non local) -> 403, jamais d'os.startfile.
    r = TestClient(app).post("/ouvrir/abc/x.xlsx")
    assert r.status_code == 403


def test_ouvrir_lance_le_fichier_en_local(monkeypatch):
    from types import SimpleNamespace

    import app.main as main_mod
    from app.extraction import charger_fixture  # noqa: F401 — dispo pour extension
    from app.generation import generer

    rapport, job_dir = generer(None, utiliser_fixture=True)
    monkeypatch.setattr(main_mod, "SORTIES_DIR", job_dir.parent)
    ouverts: list[str] = []
    monkeypatch.setattr(main_mod.os, "startfile", lambda p: ouverts.append(p), raising=False)
    req = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))

    main_mod.ouvrir_fichier(job_dir.name, rapport.fichiers[0], req)
    assert ouverts and ouverts[0].endswith(rapport.fichiers[0])
    main_mod.ouvrir_dossier(job_dir.name, req)
    assert ouverts[1].endswith(job_dir.name)


def test_imprimer_refuse_hors_poste_local():
    assert TestClient(app).post("/imprimer/abc/x.xlsx").status_code == 403


def test_imprimer_utilise_le_verbe_print_en_local(monkeypatch):
    from types import SimpleNamespace

    import app.main as main_mod
    from app.generation import generer

    rapport, job_dir = generer(None, utiliser_fixture=True)
    monkeypatch.setattr(main_mod, "SORTIES_DIR", job_dir.parent)
    appels: list[tuple] = []
    monkeypatch.setattr(main_mod.os, "startfile", lambda p, verbe=None: appels.append((p, verbe)), raising=False)
    req = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"), state=SimpleNamespace(role="admin", utilisateur="gb"))

    main_mod.imprimer_fichier(job_dir.name, rapport.fichiers[0], req)
    assert appels and appels[0][0].endswith(rapport.fichiers[0]) and appels[0][1] == "print"


def test_migration_donnees_hors_programme(tmp_path):
    """Les données d'une ancienne installation sont déplacées vers le dossier protégé,
    sans jamais écraser des données déjà présentes (réinstallation ≠ perte de données)."""
    from app.main import migrer_donnees_programme

    racine = tmp_path / "programme"
    donnees = tmp_path / "donnees"
    (racine / "runtime").mkdir(parents=True)
    (racine / "runtime" / "gb.db").write_text("ancienne base")
    (racine / ".env").write_text("ANTHROPIC_API_KEY=cle-migree")

    migrer_donnees_programme(racine=racine, donnees=donnees, runtime=donnees / "runtime")
    assert (donnees / "runtime" / "gb.db").read_text() == "ancienne base"
    assert "cle-migree" in (donnees / ".env").read_text()

    # Une nouvelle installation (programme vierge) ne touche PAS aux données migrées.
    (donnees / "runtime" / "gb.db").write_text("base vivante")
    (racine / "runtime" / "gb.db").write_text("base du vieux programme")
    migrer_donnees_programme(racine=racine, donnees=donnees, runtime=donnees / "runtime")
    assert (donnees / "runtime" / "gb.db").read_text() == "base vivante"


def test_sauvegarde_quotidienne(tmp_path, monkeypatch):
    monkeypatch.setattr(sauvegarde, "DOSSIER", tmp_path / "sauvegardes")
    db.init_db()  # crée la base isolée du test
    assert sauvegarde.sauvegarder_quotidienne() is True
    zips = list((tmp_path / "sauvegardes").glob("gb-*.zip"))
    assert len(zips) == 1
    with zipfile.ZipFile(zips[0]) as zf:
        assert "gb.db" in zf.namelist()
    # Idempotente le même jour : pas de doublon.
    assert sauvegarde.sauvegarder_quotidienne() is False
