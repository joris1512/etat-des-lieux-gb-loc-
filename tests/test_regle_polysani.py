"""Règle métier (Joris, 2026-08-31) : un GROS sanitaire collectif — plus de 3 WC ET au moins
3 urinoirs — est un POLYSANI (homme-femme, ou handi si « HANDI »).

La règle est PRIORITAIRE dans `resoudre_modele` (sinon un motif « N URINOIRS » de
`correspondances.csv` matcherait à tort quand le devis contient p.ex. « 4 PTS EAU »), SAUF si le
devis dit explicitement « GRAND SANITAIRE MIXTE » (autre modèle).
"""

from app.assemblage import resoudre_modele
from app.models import ArticleDevis


def _modele(texte: str) -> str | None:
    r = resoudre_modele(ArticleDevis(texte_ligne=texte, est_bungalow=False))
    return r[0] if r else None


def test_gros_sanitaire_devient_polysani_homme_femme():
    # Cas réel qui échouait : le « 4 » vient de « 4 PTS EAU », pas des urinoirs.
    assert _modele("SANI 15M² H/F 5WC 3 URINOIRS 4 PTS EAU") == "polysani_homme_femme.xlsx"


def test_mention_handi_donne_polysani_handi():
    assert _modele("SANI 20M2 HANDI 6WC 4 URINOIRS") == "polysani_handi.xlsx"


def test_seuil_limite_4wc_3urinoirs_est_polysani():
    assert _modele("SANI 4WC 3 URINOIRS") == "polysani_homme_femme.xlsx"


def test_pas_assez_durinoirs_nest_pas_polysani():
    # 2 urinoirs (< 3) -> la règle ne s'applique pas.
    assert _modele("SANI 4WC 2 URINOIRS") is None


def test_petit_sanitaire_nest_pas_polysani():
    # 2 WC (<= 3) -> la règle ne s'applique pas.
    assert _modele("SANI H/F 2WC 1 URINOIR") is None


def test_grand_sanitaire_mixte_reste_grand_mixte():
    # Exception explicite : « GRAND SANITAIRE MIXTE » n'est jamais transformé en polysani.
    assert _modele("GRAND SANITAIRE MIXTE 4WC 3 URINOIRS") == "sanitaire_grand_mixte.xlsx"


def test_choix_manuel_prioritaire_sur_la_regle():
    # Si l'utilisateur a choisi un modèle à la main, on le respecte (aucune règle ne l'écrase).
    art = ArticleDevis(
        texte_ligne="SANI 5WC 3 URINOIRS", est_bungalow=False, modele="sanitaire_grand_mixte.xlsx"
    )
    assert resoudre_modele(art)[0] == "sanitaire_grand_mixte.xlsx"
