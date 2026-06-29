"""Tests de normalisation et de correspondance texte -> modèle."""

from app.correspondance import est_prestation, normaliser, trouver_modele


def test_normalisation_accents_et_ponctuation():
    assert normaliser("BUNGALOW 15m2 BATISO") == "BUNGALOW 15M2 BATISO"
    assert normaliser("BUNGALOW 15 M² 2WC 2D 2U+LAVE MAINS 2PTS") == (
        "BUNGALOW 15 M2 2WC 2D 2U LAVE MAINS 2PTS"
    )


def test_bungalow_standard():
    e = trouver_modele("BUNGALOW 15m2 BATISO")
    assert e is not None
    assert e.modele == "bungalow_15m2.xlsx"
    assert e.est_bungalow is True


def test_sanitaire_pmr_gagne_sur_bungalow_generique():
    # La ligne contient « BUNGALOW 15m2 BATISO » mais le motif sanitaire PMR (plus long) doit gagner.
    e = trouver_modele("BUNGALOW 15m2 BATISO 2WC DONT 1 PMR CE15")
    assert e is not None
    assert e.modele == "sanitaire_2wc_pmr.xlsx"
    assert e.est_bungalow is False


def test_sanitaire_2wc_2d_2u():
    e = trouver_modele("BUNGALOW 15 M² 2WC 2D 2U+LAVE MAINS 2PTS")
    assert e is not None
    assert e.modele == "sanitaire_2wc_2d_2u.xlsx"
    assert e.est_bungalow is False


def test_article_inconnu():
    assert trouver_modele("CONTAINER 20 PIEDS INCONNU") is None


def test_prestations_detectees():
    assert est_prestation("5 ASSEMBLAGE DES BUNGALOWS")
    assert est_prestation("7 TRANSPORT ALLER BUNGALOWS+ESCALIER")
    assert not est_prestation("BUNGALOW 15m2 BATISO")
