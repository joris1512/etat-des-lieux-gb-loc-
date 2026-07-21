"""Isolation des tests : chaque test utilise une base + un dossier de sorties temporaires,
afin de ne jamais polluer le runtime réel (runtime/gb.db, runtime/sorties/)."""

import pytest

from app import coffre, db, generation, purge, securite
from app.config import get_reglages


@pytest.fixture(autouse=True)
def _isoler_runtime(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "gb.db")
    db._pret = False
    sorties = tmp_path / "sorties"
    monkeypatch.setattr(generation, "SORTIES_DIR", sorties)
    monkeypatch.setattr(purge, "SORTIES_DIR", sorties)
    # Coffre à secrets (session, SMTP) isolé : pas d'écriture dans le runtime réel.
    monkeypatch.setattr(coffre, "RUNTIME_DIR", tmp_path / "runtime")
    # Auth neutralisée par défaut : la suite ne dépend pas du .env du poste (un GB_PASSWORD
    # défini en local ne doit pas casser les tests). Les tests d'auth la réactivent eux-mêmes.
    monkeypatch.setenv("GB_PASSWORD", "")
    monkeypatch.setenv("GB_PASSWORD_HASH", "")
    get_reglages.cache_clear()
    securite._echecs.clear()  # anti-force-brute : pas d'état partagé entre tests
    yield
    get_reglages.cache_clear()
    db._pret = False
    securite._echecs.clear()
