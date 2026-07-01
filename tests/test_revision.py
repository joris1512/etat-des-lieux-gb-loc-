"""Tests de l'étape de révision : analyser sans générer, puis générer depuis une extraction révisée."""

from app import db
from app.extraction import charger_fixture
from app.generation import generer_depuis_extraction
from app.main import _apercu


def test_apercu_compte_sans_generer():
    ext = charger_fixture()
    ap = _apercu(ext)
    assert ap["total"] == 17
    assert ap["assembles"] == 4
    assert ap["sanitaires"] == 2
    assert ap["non_reconnus"] == []


def test_exclure_un_module_reduit_le_plan():
    ext = charger_fixture()
    ext.articles = ext.articles[:-1]  # retire le module GARDIEN
    rapport, _ = generer_depuis_extraction(ext)
    assert len(rapport.fichiers) == 16


def test_entete_revisee_enrichit_la_base():
    ext = charger_fixture()
    ext.entete.client = "CLIENT CORRIGÉ"
    ext.entete.numero_client = "Z9"
    generer_depuis_extraction(ext)
    clients = db.lister_clients()
    assert any(c["numero_client"] == "Z9" and c["raison_sociale"] == "CLIENT CORRIGÉ" for c in clients)


def test_override_modele_par_module():
    from app.assemblage import construire_plan

    ext = charger_fixture()
    ext.articles[0].modele = "sanitaire_1wc.xlsx"  # choix manuel de l'utilisateur
    plan = construire_plan(ext)
    assert any(e.modele == "sanitaire_1wc.xlsx" for e in plan.etats)


def test_mobilier_revise_est_pris_en_compte():
    ext = charger_fixture()
    # Force une quantité de mobilier sur le premier module qui en a.
    for art in ext.articles:
        if art.mobilier:
            art.mobilier[0].quantite = 999
            break
    rapport, _ = generer_depuis_extraction(ext)
    assert len(rapport.fichiers) == 17  # le plan reste valide
