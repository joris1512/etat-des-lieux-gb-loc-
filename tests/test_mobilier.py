"""Le mobilier est ÉCRIT sur les lignes d'inventaire des vrais modèles (quantités par libellé)."""

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


def test_vestiaire_recoit_ses_armoires():
    # VESTIAIRE HOMMES : 10 armoires doubles -> ligne d'inventaire du modèle « avec mobiliers ».
    rapport, job_dir, par_nom = _plan_et_fichiers()
    nom = next(
        n for n, e in par_nom.items()
        if e.bloc == "VESTIAIRE HOMMES" and n in rapport.fichiers
    )
    a46 = str(_ws(job_dir, nom)["A46"].value)
    assert "Armoires doubles : 10" in a46
    assert "Chaises" in a46  # les autres libellés restent en place (sans quantité)


def test_salle_reunion_assemblee_recoit_chaises_et_tables():
    # SALLE DE REUNION (pas de kitchenette) -> assemblé classique avec lignes A43-A45.
    rapport, job_dir, par_nom = _plan_et_fichiers()
    nom = next(
        n for n, e in par_nom.items()
        if e.type_etat == "assemble" and e.bloc == "SALLE DE REUNION" and n in rapport.fichiers
    )
    ws = _ws(job_dir, nom)
    assert str(ws["A43"].value) == "Chaise : 20"
    assert str(ws["A44"].value) == "Table : 4"
    assert str(ws["A45"].value) == "Armoire doubles : 1"


def test_refectoire_assemble_kit_recoit_evier():
    rapport, job_dir, par_nom = _plan_et_fichiers()
    nom = next(
        n for n, e in par_nom.items()
        if e.type_etat == "assemble" and e.bloc == "REFECTOIRE" and n in rapport.fichiers
    )
    ws = _ws(job_dir, nom)
    assert str(ws["A36"].value) == "Evier : 2"


def test_mobilier_sans_ligne_est_signale():
    # Les bancs du vestiaire n'ont pas de ligne sur « avec mobiliers » -> avertissement visible.
    rapport, _job_dir, _ = _plan_et_fichiers()
    assert any("BANC" in a and "non rattaché" in a for a in rapport.avertissements)
