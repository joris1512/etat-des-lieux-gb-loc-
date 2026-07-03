"""Le mobilier du devis est reporté INTÉGRALEMENT, tel quel, sur les états des lieux."""

from openpyxl import load_workbook

from app.assemblage import construire_plan
from app.extraction import charger_fixture
from app.generation import generer


def _plan_et_fichiers():
    rapport, job_dir = generer(None, utiliser_fixture=True)
    par_nom = {e.nom_fichier: e for e in construire_plan(charger_fixture()).etats}
    return rapport, job_dir, par_nom


def _ws(job_dir, nom):
    wb = load_workbook(job_dir / nom)
    return wb[wb.sheetnames[0]]


def test_vestiaire_recoit_tout_son_mobilier_tel_quel():
    # VESTIAIRE HOMMES : 10 armoires + 2 bancs -> TOUT est écrit, désignations du devis incluses.
    rapport, job_dir, par_nom = _plan_et_fichiers()
    nom = next(
        n for n, e in par_nom.items()
        if e.bloc == "VESTIAIRE HOMMES" and n in rapport.fichiers
    )
    a46 = str(_ws(job_dir, nom)["A46"].value)
    assert "ARMOIRE DOUBLE VESTIAIRE : 10" in a46
    assert "BANC PLIANT 1.60M BOIS STRUCTURE METAL : 2" in a46  # même sans ligne pré-imprimée


def test_salle_reunion_assemblee_liste_complete():
    rapport, job_dir, par_nom = _plan_et_fichiers()
    nom = next(
        n for n, e in par_nom.items()
        if e.type_etat == "assemble" and e.bloc == "SALLE DE REUNION" and n in rapport.fichiers
    )
    ws = _ws(job_dir, nom)
    lignes = [str(ws[f"A{r}"].value) for r in range(43, 48)]
    assert any("TABLE MODULAIRE RECT. 160X80 : 4" in x for x in lignes)
    assert any("CHAISE COQUE : 20" in x for x in lignes)
    assert any("ARMOIRE BASSE" in x and ": 1" in x for x in lignes)


def test_refectoire_mixte_va_sur_assemble_classique_et_liste_tout():
    # Mobilier mixte (tables + bancs + kitchenette) -> assemblé CLASSIQUE (5 lignes), pas le kit.
    rapport, job_dir, par_nom = _plan_et_fichiers()
    etat = next(
        e for e in par_nom.values()
        if e.type_etat == "assemble" and e.bloc == "REFECTOIRE"
    )
    assert etat.modele == "bungalow_assemble.xlsx"
    ws = _ws(job_dir, etat.nom_fichier)
    contenu = " | ".join(str(ws[f"A{r}"].value) for r in range(43, 48))
    for attendu in ("TABLE MODULAIRE", "BANC PLIANT", "REFRIGERATEUR", "MICRO ONDES", "EVIER"):
        assert attendu in contenu  # rien n'est perdu, même frigo/micro-ondes


def test_aucun_avertissement_mobilier_sur_eiffage():
    rapport, _job_dir, _ = _plan_et_fichiers()
    assert not any("rattach" in a.lower() for a in rapport.avertissements)


def test_kit_reste_choisi_quand_kitchenette_seule():
    from app.assemblage import _kitchenette_seulement
    from app.models import MobilierItem

    frigo = [MobilierItem(designation="ACCESSOIRE REFRIGERATEUR", quantite=1)]
    mixte = frigo + [MobilierItem(designation="TABLE MODULAIRE", quantite=2)]
    assert _kitchenette_seulement(frigo) is True
    assert _kitchenette_seulement(mixte) is False
    assert _kitchenette_seulement([]) is False
