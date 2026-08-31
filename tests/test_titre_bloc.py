"""Règle métier (Joris, 2026-08-31) : reporter le CONTENU réel du bloc dans le TITRE de l'état
des lieux. Sur les polysani, la cellule-titre A6 est réécrite à partir de la ligne du devis
(« 5WC / 3UR / 4 PTS EAU ») au lieu du texte figé du modèle.

Piloté par `titre_contenu` dans config/cellules.yaml (cellule + gabarit).
"""

from openpyxl import load_workbook

from app.config import TEMPLATES_DIR
from app.models import EnteteDevis, EtatDesLieux
from app.remplissage import remplir_etat, resumer_contenu_bloc

ENTETE = EnteteDevis(
    client="ACME", titre_chantier="Chantier", adresse="1 rue X",
    code_postal="30000", ville="NIMES", numero_offre="OF-1",
)


# --- resumer_contenu_bloc (fonction pure) ---

def test_resume_wc_urinoirs_points_eau():
    assert resumer_contenu_bloc("SANI 15M² H/F 5WC 3 URINOIRS 4 PTS EAU") == "5WC / 3UR / 4 PTS EAU"


def test_resume_wc_urinoirs_seuls():
    assert resumer_contenu_bloc("SANI 20M2 HANDI 6WC 4 URINOIRS") == "6WC / 4UR"


def test_resume_lavabos_reconnus():
    assert resumer_contenu_bloc("BLOC 6WC 2 URINOIRS 2 LAVABOS") == "6WC / 2UR / 2 LAVABOS"
    assert resumer_contenu_bloc("SANI 4WC 3 URIN 2 LAVE MAINS") == "4WC / 3UR / 2 LAVABOS"


def test_resume_vide_si_rien_de_sanitaire():
    assert resumer_contenu_bloc("BUNGALOW 15M2 BATISO") == ""


# --- Génération réelle sur les modèles (source lue seule, sortie en tmp_path) ---

def _generer_et_lire(tmp_path, modele, feuille, texte):
    out = tmp_path / f"out_{modele}"
    etat = EtatDesLieux(modele=modele, type_etat="sanitaire", texte_ligne=texte, nom_fichier="t")
    remplir_etat(TEMPLATES_DIR / modele, out, ENTETE, etat)
    return load_workbook(out)[feuille]["A6"].value


def test_titre_polysani_homme_femme_reecrit(tmp_path):
    a6 = _generer_et_lire(
        tmp_path, "polysani_homme_femme.xlsx", "Polysani Homme-Femme",
        "SANI 15M² H/F 5WC 3 URINOIRS 4 PTS EAU",
    )
    assert a6 == "Sanitaire : BLOC 5WC / 3UR / 4 PTS EAU (POLYSANI)"


def test_titre_polysani_handi_reecrit(tmp_path):
    a6 = _generer_et_lire(
        tmp_path, "polysani_handi.xlsx", "Polysani H", "SANI 20M2 HANDI 6WC 4 URINOIRS",
    )
    assert a6 == "Sanitaire : 6WC / 4UR (POLYSANI HANDI)"


def test_titre_inchange_si_contenu_illisible(tmp_path):
    # Ligne sans WC/urinoirs -> on garde le titre figé du modèle (pas de réécriture hasardeuse).
    a6 = _generer_et_lire(
        tmp_path, "polysani_homme_femme.xlsx", "Polysani Homme-Femme", "SANITAIRES COLLECTIFS",
    )
    assert "(POLYSANI)" in a6  # titre d'origine conservé
