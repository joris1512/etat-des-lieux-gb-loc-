"""Détection de la fonction du bungalow depuis le bloc + report sur le plan."""

from app.assemblage import construire_plan
from app.extraction import charger_fixture
from app.fonctions import detecter_fonction
from app.models import ArticleDevis, EnteteDevis, ExtractionDevis

ENTETE = EnteteDevis(client="X", titre_chantier="Y", adresse="Z", code_postal="00000")


def test_detecte_les_quatre_fonctions():
    assert detecter_fonction("2 BUREAUX INDEPENDANTS") == "BUREAU"
    assert detecter_fonction("VESTIAIRE HOMMES") == "VESTIAIRE"
    assert detecter_fonction("REFECTOIRE") == "REFECTOIRE"
    assert detecter_fonction("SALLE DE REUNION") == "SALLE DE REUNION"


def test_insensible_a_la_casse_et_aux_accents():
    assert detecter_fonction("salle de réunion") == "SALLE DE REUNION"
    assert detecter_fonction("Réfectoire") == "REFECTOIRE"


def test_bloc_sans_fonction_renvoie_none():
    assert detecter_fonction("GARDIEN") is None
    assert detecter_fonction("SANITAIRES") is None
    assert detecter_fonction("H/F WC") is None
    assert detecter_fonction(None) is None
    assert detecter_fonction("") is None


def test_fonction_reportee_sur_chaque_etat_du_bloc():
    # Deux bungalows REFECTOIRE sans ligne d'assemblage -> 2 individuels, tous en fonction REFECTOIRE.
    arts = [
        ArticleDevis(texte_ligne="BUNGALOW 15m2 BATISO", bloc="REFECTOIRE", est_bungalow=True),
        ArticleDevis(texte_ligne="BUNGALOW 15m2 BATISO", bloc="REFECTOIRE", est_bungalow=True),
    ]
    plan = construire_plan(ExtractionDevis(entete=ENTETE, articles=arts))
    assert {e.fonction for e in plan.etats} == {"REFECTOIRE"}


def test_fonctions_du_plan_eiffage():
    plan = construire_plan(charger_fixture())
    par_bloc = {e.bloc: e.fonction for e in plan.etats if e.type_etat == "assemble"}
    assert par_bloc["REFECTOIRE"] == "REFECTOIRE"
    assert par_bloc["2 BUREAUX INDEPENDANTS"] == "BUREAU"
    assert par_bloc["2 BUREAUX"] == "BUREAU"
    assert par_bloc["SALLE DE REUNION"] == "SALLE DE REUNION"
    # Un sanitaire n'a pas de fonction de bungalow.
    assert all(e.fonction is None for e in plan.etats if e.type_etat == "sanitaire")
    # Le bloc « GARDIEN » n'a pas de fonction reconnue : ligne laissée telle quelle.
    gardien = next(e for e in plan.etats if e.bloc == "GARDIEN")
    assert gardien.fonction is None
