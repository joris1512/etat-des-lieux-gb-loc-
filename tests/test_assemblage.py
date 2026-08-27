"""Tests de la logique d'assemblage sur des cas ciblés (règles R4 assemblage + R10 mobilier)."""

from app.assemblage import construire_plan
from app.models import ArticleDevis, EnteteDevis, ExtractionDevis, MobilierItem

ENTETE = EnteteDevis(
    client="X", titre_chantier="Y", adresse="Z", code_postal="00000", numero_offre="TEST"
)


def _bung(bloc, mobilier=None, assemble=False):
    return ArticleDevis(
        texte_ligne="BUNGALOW 15m2 BATISO",
        bloc=bloc,
        est_bungalow=True,
        mobilier=mobilier or [],
        assemble=assemble,
    )


def _wc(quantite=1):
    return ArticleDevis(texte_ligne="WC AUTONOME", est_bungalow=False, quantite=quantite)


def test_bloc_unique_donne_un_individuel():
    plan = construire_plan(ExtractionDevis(entete=ENTETE, articles=[_bung("GARDIEN")]))
    assert len(plan.etats) == 1
    assert plan.etats[0].type_etat == "individuel"


def test_deux_bungalows_sans_ligne_assemblage_restent_individuels():
    # R4 : 2 bungalows identiques d'affilée SANS ligne d'assemblage => 2 individuels (aucun assemblé).
    arts = [
        _bung("VESTIAIRE"),
        _bung("VESTIAIRE", [MobilierItem(designation="ARMOIRE DOUBLE VESTIAIRE", quantite=12)]),
    ]
    plan = construire_plan(ExtractionDevis(entete=ENTETE, articles=arts))
    assert [e.type_etat for e in plan.etats] == ["individuel", "individuel"]
    # R10 : 12 armoires réparties à parts égales -> 6 + 6.
    assert [sum(m.quantite for m in e.mobilier) for e in plan.etats] == [6, 6]


def test_deux_bungalows_avec_ligne_assemblage_donnent_assemble_plus_deux():
    # R4 : AVEC la ligne d'assemblage (assemble=True) => 1 assemblé + 2 individuels.
    arts = [
        _bung("REFECTOIRE", assemble=True),
        _bung(
            "REFECTOIRE",
            [MobilierItem(designation="TABLE MODULAIRE RECT. 160X80", quantite=4)],
            assemble=True,
        ),
    ]
    plan = construire_plan(ExtractionDevis(entete=ENTETE, articles=arts))
    assert [e.type_etat for e in plan.etats] == ["assemble", "individuel", "individuel"]
    assemble = plan.etats[0]
    assert assemble.nb_modules == 2
    assert assemble.mobilier == []  # l'assemblé ne porte jamais de mobilier
    # R10 : 4 tables réparties -> 2 + 2 sur les individuels.
    assert [sum(m.quantite for m in e.mobilier) for e in plan.etats[1:]] == [2, 2]


def test_mobilier_refectoire_reparti_a_parts_egales():
    # D1 RAYONIER : 2 réfectoires, 4 tables + 16 chaises au TOTAL -> 2+2 tables et 8+8 chaises.
    mob = [
        MobilierItem(designation="TABLE MODULAIRE RECT. 160X80", quantite=4),
        MobilierItem(designation="CHAISE COQUE", quantite=16),
    ]
    arts = [_bung("REFECTOIRE"), _bung("REFECTOIRE", mob)]
    plan = construire_plan(ExtractionDevis(entete=ENTETE, articles=arts))
    assert [e.type_etat for e in plan.etats] == ["individuel", "individuel"]
    for e in plan.etats:
        tables = sum(m.quantite for m in e.mobilier if "TABLE" in m.designation.upper())
        chaises = sum(m.quantite for m in e.mobilier if "CHAISE" in m.designation.upper())
        assert (tables, chaises) == (2, 8)


def test_blocs_differents_ne_fusionnent_pas():
    # 1 bureau indépendant (seul) puis 2 bureaux assemblés : les blocs ne se regroupent pas entre eux.
    arts = [
        _bung("1 BUREAU INDEPENDANT"),
        _bung("2 BUREAUX", assemble=True),
        _bung("2 BUREAUX", assemble=True),
    ]
    plan = construire_plan(ExtractionDevis(entete=ENTETE, articles=arts))
    types = [e.type_etat for e in plan.etats]
    assert types == ["individuel", "assemble", "individuel", "individuel"]


def test_sanitaire_coupe_le_run():
    arts = [
        _bung("REFECTOIRE", assemble=True),
        ArticleDevis(
            texte_ligne="BUNGALOW 15 M² 2WC 2D 2U+LAVE MAINS 2PTS",
            bloc="SANITAIRES",
            est_bungalow=False,
        ),
        _bung("REFECTOIRE", assemble=True),
    ]
    plan = construire_plan(ExtractionDevis(entete=ENTETE, articles=arts))
    # Deux REFECTOIRE séparés par un sanitaire => deux runs de 1 (individuels) + 1 sanitaire.
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


def test_wc_autonomes_regroupes_par_trois():
    # R2 (D1 RAYONIER) : 6 WC autonomes (6 lignes) => 2 états de 3.
    plan = construire_plan(ExtractionDevis(entete=ENTETE, articles=[_wc() for _ in range(6)]))
    wc = [e for e in plan.etats if e.type_etat == "sanitaire"]
    assert len(wc) == 2
    assert [e.nb_modules for e in wc] == [3, 3]


def test_wc_autonomes_reste_et_unite():
    # 4 WC -> 2 états (3 + 1) ; 1 WC -> 1 état (1 emplacement).
    plan4 = construire_plan(ExtractionDevis(entete=ENTETE, articles=[_wc() for _ in range(4)]))
    assert [e.nb_modules for e in plan4.etats if e.type_etat == "sanitaire"] == [3, 1]
    plan1 = construire_plan(ExtractionDevis(entete=ENTETE, articles=[_wc()]))
    assert [e.nb_modules for e in plan1.etats] == [1]


def test_wc_autonomes_exprimes_en_quantite():
    # WC autonomes exprimés en UNE ligne quantité 6 => 2 états de 3 (même résultat).
    plan = construire_plan(ExtractionDevis(entete=ENTETE, articles=[_wc(quantite=6)]))
    assert [e.nb_modules for e in plan.etats if e.type_etat == "sanitaire"] == [3, 3]


def test_report_options_devis_clim_elingage_doses_douches():
    # Clim (par bungalow), élingage bas (global), doses réparties (R3), nb douches (R1).
    entete = EnteteDevis(
        client="X", titre_chantier="Y", adresse="Z", code_postal="00000", numero_offre="T",
        elingage_point_bas=True, doses_wc_supplementaires=24,
    )
    arts = (
        [ArticleDevis(texte_ligne="BUNGALOW 15m2 BATISO", bloc="BUREAU",
                      est_bungalow=True, climatisation=True)]
        + [_wc() for _ in range(6)]
        + [ArticleDevis(texte_ligne="PETIT SANITAIRE W4D (4 DOUCHES)", est_bungalow=False)]
    )
    plan = construire_plan(ExtractionDevis(entete=entete, articles=arts))
    bung = next(e for e in plan.etats if e.type_etat == "individuel")
    assert bung.climatisation is True and bung.elingage_bas is True
    wc = [e for e in plan.etats if "AUTONOME" in e.modele.upper()]
    assert len(wc) == 2 and all(e.doses == 12 for e in wc)  # 24 doses / 2 états
    douche = next(e for e in plan.etats if "DOUCHE" in e.texte_ligne.upper())
    assert douche.nb_douches == 4


def test_wc_autonomes_series_separees_par_un_bungalow():
    # Un bungalow interrompt la série : 2 WC, 1 bungalow, 2 WC => 1 état (2) + 1 individuel + 1 état (2).
    arts = [_wc(), _wc(), _bung("GARDIEN"), _wc(), _wc()]
    plan = construire_plan(ExtractionDevis(entete=ENTETE, articles=arts))
    types = [e.type_etat for e in plan.etats]
    assert types == ["sanitaire", "individuel", "sanitaire"]
    wc = [e.nb_modules for e in plan.etats if e.type_etat == "sanitaire"]
    assert wc == [2, 2]
