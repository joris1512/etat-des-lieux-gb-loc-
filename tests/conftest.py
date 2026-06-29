"""Isolation des tests : chaque test utilise une base + un dossier de sorties temporaires,
afin de ne jamais polluer le runtime réel (runtime/gb.db, runtime/sorties/)."""

import pytest

from app import db, generation, purge, securite


@pytest.fixture(autouse=True)
def _isoler_runtime(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "gb.db")
    db._pret = False
    sorties = tmp_path / "sorties"
    monkeypatch.setattr(generation, "SORTIES_DIR", sorties)
    monkeypatch.setattr(purge, "SORTIES_DIR", sorties)
    securite._echecs.clear()  # anti-force-brute : pas d'état partagé entre tests
    yield
    db._pret = False
    securite._echecs.clear()
