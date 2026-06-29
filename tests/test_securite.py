"""Tests de l'authentification optionnelle et de la purge des sorties."""

import os
import time

import pytest
from fastapi.testclient import TestClient

from app import purge
from app.config import get_reglages
from app.main import app


@pytest.fixture
def client_protege(monkeypatch):
    """Client avec mot de passe activé (réinitialise le cache de réglages avant/après)."""
    monkeypatch.setenv("GB_PASSWORD", "secret")
    get_reglages.cache_clear()
    yield TestClient(app)
    get_reglages.cache_clear()


def test_auth_desactivee_par_defaut():
    # Sans GB_PASSWORD, l'appli est ouverte (utile en dev/démo).
    get_reglages.cache_clear()
    assert TestClient(app).get("/modeles").status_code == 200


def test_auth_sans_identifiants_401(client_protege):
    assert client_protege.get("/modeles").status_code == 401


def test_auth_mauvais_mot_de_passe_401(client_protege):
    assert client_protege.get("/modeles", auth=("gb", "nope")).status_code == 401


def test_auth_bons_identifiants_200(client_protege):
    assert client_protege.get("/modeles", auth=("gb", "secret")).status_code == 200


def test_password_vide_equivaut_a_desactive(monkeypatch):
    # GB_PASSWORD présent mais vide/blanc => normalisé à None (auth désactivée, pas de fail-open ambigu).
    monkeypatch.setenv("GB_PASSWORD", "   ")
    get_reglages.cache_clear()
    try:
        assert get_reglages().mot_de_passe is None
        assert TestClient(app).get("/modeles").status_code == 200
    finally:
        get_reglages.cache_clear()


def test_purge_supprime_les_anciens(monkeypatch, tmp_path):
    monkeypatch.setattr(purge, "SORTIES_DIR", tmp_path)
    vieux = tmp_path / "vieux_job"
    vieux.mkdir()
    (vieux / "f.xlsx").write_text("x")
    neuf = tmp_path / "nouveau_job"
    neuf.mkdir()

    vieille_date = time.time() - 5 * 3600
    os.utime(vieux, (vieille_date, vieille_date))

    supprimes = purge.purger_anciennes_sorties(max_age_heures=1)
    assert supprimes == 1
    assert not vieux.exists()
    assert neuf.exists()
