"""Tests de la logique d'assemblage sur des cas ciblés."""

from app.assemblage import construire_plan
from app.models import ArticleDevis, EnteteDevis, ExtractionDevis, MobilierItem

ENTETE = EnteteDevis(
    client="X", titre_chantier="Y", adresse="Z", code_postal="00000", numero_offre="TEST"
)


def _bung(bloc, mobilier=None):
    return ArticleDevis(
        texte_ligne="BUNGALOW 15m2 BATISO",
        bloc=bloc,
        est_bungalow=True,
        mobilier=mobilier or [],
    )


def test_bloc_unique_donne_un_individuel():
    plan = construire_plan(ExtractionDevis(entete=ENTETE, articles=[_bung("GARDIEN")]))
    assert len(plan.etats) == 1
    assert plan.etats[0].type_etat == "individuel"


def test_deux_bungalows_meme_bloc_donnent_assemble_plus_deux():
    arts = [
        _bung("REFECTOIRE"),
        _bung("REFECTOIRE", [MobilierItem(designation="TABLE MODULAIRE RECT. 160X80", quantite=4)]),
    ]
    plan = construire_plan(ExtractionDevis(entete=ENTETE, articles=arts))
    types = [e.type_etat for e in plan.etats]
    assert types == ["assemble", "individuel", "individuel"]
    # Le mobilier va sur les INDIVIDUELS (chacun garde SA ligne de devis), jamais sur l'assemblé.
    assemble = plan.etats[0]
    assert assemble.nb_modules == 2
    assert assemble.mobilier == []
    assert plan.etats[1].mobilier == []  # 1er module : pas de mobilier au devis
    assert sum(m.quantite for m in plan.etats[2].mobilier) == 4  # 2e module : ses 4 tables


def test_blocs_differents_ne_fusionnent_pas():
    # 1 bureau indépendant (1) puis 2 bureaux (2) : ne doivent pas se regrouper.
    arts = [_bung("1 BUREAU INDEPENDANT"), _bung("2 BUREAUX"), _bung("2 BUREAUX")]
    plan = construire_plan(ExtractionDevis(entete=ENTETE, articles=arts))
    types = [e.type_etat for e in plan.etats]
    assert types == ["individuel", "assemble", "individuel", "individuel"]


def test_sanitaire_coupe_le_run():
    arts = [
        _bung("REFECTOIRE"),
        ArticleDevis(
            texte_ligne="BUNGALOW 15 M² 2WC 2D 2U+LAVE MAINS 2PTS",
            bloc="SANITAIRES",
            est_bungalow=False,
        ),
        _bung("REFECTOIRE"),
    ]
    plan = construire_plan(ExtractionDevis(entete=ENTETE, articles=arts))
    # Deux REFECTOIRE séparés par un sanitaire => deux runs de 1 + 1 sanitaire = 3 individuels.
    types = [e.type_etat for e in plan.etats]
    assert types == ["individuel", "sanitaire", "individuel"]


def test_prestations_ignorees_sans_etre_non_reconnues():
    arts = [
        _bung("GARDIEN"),
        ArticleDevis(texte_ligne="5 ASSEMBLAGE DES BUNGALOWS", est_bungalow=False),
    ]
    plan = construire_plan(ExtractionDevis(entete=ENTETE, articles=arts))
    assert len(plan.etats) == 1
    assert plan.non_reconnus == []
