"""Tests de la gestion des modèles (validation des noms/contenus, liste des attendus)."""

import pytest

from app.modeles import _valider_nom, enregistrer_modele, modeles_attendus


def test_modeles_attendus_inclut_correspondances_et_assemble():
    attendus = modeles_attendus()
    assert "bungalow_15m2.xlsx" in attendus
    assert "bungalow_assemble.xlsx" in attendus
    assert "sanitaire_2wc_pmr.xlsx" in attendus


def test_valider_nom_refuse_non_xlsx():
    with pytest.raises(ValueError):
        _valider_nom("modele.pdf")


def test_valider_nom_neutralise_le_chemin():
    # Toute tentative d'évasion de dossier est réduite au simple nom de base.
    assert _valider_nom("../../secret.xlsx") == "secret.xlsx"
    assert _valider_nom("dossier\\modele.xlsx") == "modele.xlsx"


def test_enregistrer_refuse_contenu_non_excel():
    with pytest.raises(ValueError):
        enregistrer_modele("faux.xlsx", b"ceci n'est pas un classeur")


def test_enregistrer_refuse_fichier_vide():
    with pytest.raises(ValueError):
        enregistrer_modele("vide.xlsx", b"")
