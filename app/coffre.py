"""Coffre à secrets locaux : secrets réutilisables (secret de signature des sessions, mot de
passe SMTP) stockés dans des fichiers à droits restreints (0600) DANS `runtime/`, jamais dans
la base SQLite ni dans les sauvegardes.

Raison : `gb.db` est copié par les sauvegardes (deploy/sauvegarde.sh) et rapatrié hors serveur.
Un secret de session dans la base permettrait de forger des cookies ; un mot de passe SMTP en
clair serait exploitable. Ces fichiers, eux, ne sont pas inclus dans les sauvegardes.
"""

from __future__ import annotations

import os
import stat

from app.config import RUNTIME_DIR


def _fichier(nom: str):
    return RUNTIME_DIR / f"{nom}.secret"


def lire(nom: str) -> str | None:
    f = _fichier(nom)
    if f.exists():
        return f.read_text(encoding="utf-8")
    return None


def ecrire(nom: str, valeur: str) -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    f = _fichier(nom)
    f.write_text(valeur, encoding="utf-8")
    try:  # 0600 : lisible par le seul propriétaire (sans effet notable sous Windows, ok sous Linux)
        os.chmod(f, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def effacer(nom: str) -> None:
    _fichier(nom).unlink(missing_ok=True)
