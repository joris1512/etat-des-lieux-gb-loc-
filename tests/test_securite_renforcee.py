"""Tests du durcissement sécurité : en-têtes, hachage, anti-force-brute."""

from fastapi.testclient import TestClient

from app import securite
from app.config import get_reglages
from app.main import app
from app.securite import hacher, verifier_hash


def test_entetes_securite_presents():
    get_reglages.cache_clear()
    r = TestClient(app).get("/")
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]


def test_hachage_roundtrip():
    h = hacher("Sup3r-Secret!")
    assert h.startswith("pbkdf2_sha256$")
    assert verifier_hash("Sup3r-Secret!", h)
    assert not verifier_hash("mauvais", h)


def test_hash_invalide_ne_plante_pas():
    assert verifier_hash("x", "format_invalide") is False


def test_auth_par_mot_de_passe_hache(monkeypatch):
    h = hacher("motdepasse")
    monkeypatch.setenv("GB_PASSWORD_HASH", h)
    monkeypatch.delenv("GB_PASSWORD", raising=False)
    get_reglages.cache_clear()
    securite._echecs.clear()
    try:
        c = TestClient(app)
        assert c.get("/modeles").status_code == 401
        assert c.get("/modeles", auth=("gb", "mauvais")).status_code == 401
        assert c.get("/modeles", auth=("gb", "motdepasse")).status_code == 200
    finally:
        get_reglages.cache_clear()
        securite._echecs.clear()


def test_anti_force_brute_bloque_apres_n_echecs(monkeypatch):
    monkeypatch.setenv("GB_PASSWORD", "secret")
    get_reglages.cache_clear()
    securite._echecs.clear()
    try:
        c = TestClient(app)
        for _ in range(securite._MAX_ECHECS):
            assert c.get("/modeles", auth=("gb", "faux")).status_code == 401
        # Au-delà du seuil : blocage (429), même avec les BONS identifiants.
        assert c.get("/modeles", auth=("gb", "secret")).status_code == 429
    finally:
        get_reglages.cache_clear()
        securite._echecs.clear()
