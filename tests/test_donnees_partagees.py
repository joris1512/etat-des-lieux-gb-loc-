"""Données partagées sur le serveur : migration de l'ancien poste + détection réseau."""

import sqlite3
from pathlib import Path

from app import main
from app.config import _est_reseau


def _fabriquer_ancienne_base(dossier: Path) -> None:
    """Crée une ancienne installation (runtime/gb.db + un fichier de sortie + .env)."""
    runtime = dossier / "runtime"
    (runtime / "sorties").mkdir(parents=True)
    cx = sqlite3.connect(runtime / "gb.db")
    cx.execute("CREATE TABLE t (v TEXT)")
    cx.execute("INSERT INTO t VALUES ('donnee-du-poste')")
    cx.commit()
    cx.close()
    (runtime / "sorties" / "vieux.txt").write_text("archive", encoding="utf-8")
    (dossier / ".env").write_text("ANTHROPIC_API_KEY=cle-test\n", encoding="utf-8")


def test_migration_depuis_ancien_poste(tmp_path, monkeypatch):
    ancien = tmp_path / "ancien"       # %LOCALAPPDATA%\GB Etats des lieux - donnees
    partage = tmp_path / "serveur"     # dossier partagé du serveur
    _fabriquer_ancienne_base(ancien)
    monkeypatch.setattr(main, "DONNEES_DIR", partage)
    monkeypatch.setattr(main, "RUNTIME_DIR", partage / "runtime")

    main.migrer_depuis_ancien_dossier(ancien=ancien, runtime=partage / "runtime")

    # La base et les fichiers du poste se retrouvent dans le dossier partagé.
    base = partage / "runtime" / "gb.db"
    assert base.is_file()
    cx = sqlite3.connect(base)
    assert cx.execute("SELECT v FROM t").fetchone()[0] == "donnee-du-poste"
    cx.close()
    assert (partage / "runtime" / "sorties" / "vieux.txt").is_file()
    assert (partage / ".env").read_text(encoding="utf-8").startswith("ANTHROPIC_API_KEY=")


def test_migration_ne_pas_ecraser_le_partage(tmp_path, monkeypatch):
    """Si le dossier partagé a DÉJÀ une base (rempli par un autre poste), on n'écrase rien."""
    ancien = tmp_path / "ancien"
    partage = tmp_path / "serveur"
    _fabriquer_ancienne_base(ancien)
    (partage / "runtime").mkdir(parents=True)
    cx = sqlite3.connect(partage / "runtime" / "gb.db")
    cx.execute("CREATE TABLE t (v TEXT)")
    cx.execute("INSERT INTO t VALUES ('base-serveur-existante')")
    cx.commit()
    cx.close()
    monkeypatch.setattr(main, "DONNEES_DIR", partage)

    main.migrer_depuis_ancien_dossier(ancien=ancien, runtime=partage / "runtime")

    cx = sqlite3.connect(partage / "runtime" / "gb.db")
    assert cx.execute("SELECT v FROM t").fetchone()[0] == "base-serveur-existante"
    cx.close()


def test_detection_reseau():
    # Un chemin UNC est reconnu comme réseau ; un dossier temporaire local ne l'est pas.
    assert _est_reseau(Path(r"\\serveur\partage\gb")) is True
    import tempfile

    assert _est_reseau(Path(tempfile.gettempdir())) is False
