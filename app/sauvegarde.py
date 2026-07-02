"""Sauvegarde automatique de la base de connaissance (une par jour, 14 conservées).

À chaque démarrage de l'application, si aucune sauvegarde n'existe pour aujourd'hui, la base
SQLite est copiée proprement (API de backup SQLite : cohérente même base ouverte) puis zippée
dans runtime/sauvegardes/. Restauration : dézipper et remplacer runtime/gb.db (app arrêtée).
"""

from __future__ import annotations

import logging
import sqlite3
import zipfile
from datetime import date

from app import db
from app.config import RUNTIME_DIR

logger = logging.getLogger("uvicorn.error")

DOSSIER = RUNTIME_DIR / "sauvegardes"
A_CONSERVER = 14  # ~2 semaines de sauvegardes quotidiennes


def sauvegarder_quotidienne() -> bool:
    """Crée la sauvegarde du jour si absente. Renvoie True si une sauvegarde a été créée."""
    if not db.DB_PATH.exists():
        return False
    cible = DOSSIER / f"gb-{date.today().isoformat()}.zip"
    if cible.exists():
        return False
    DOSSIER.mkdir(parents=True, exist_ok=True)

    # Copie cohérente via l'API de backup SQLite (fonctionne même si la base est utilisée).
    tmp = DOSSIER / "_gb_backup.db"
    src = sqlite3.connect(db.DB_PATH)
    try:
        dst = sqlite3.connect(tmp)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    try:
        with zipfile.ZipFile(cible, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(tmp, arcname="gb.db")
    finally:
        tmp.unlink(missing_ok=True)

    # Rotation : on garde les N plus récentes.
    sauvegardes = sorted(DOSSIER.glob("gb-*.zip"))
    for ancienne in sauvegardes[:-A_CONSERVER]:
        ancienne.unlink(missing_ok=True)
    logger.info("Sauvegarde quotidienne de la base créée : %s", cible.name)
    return True
