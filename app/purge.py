"""Purge automatique des fichiers générés (runtime/sorties) plus vieux qu'un seuil."""

from __future__ import annotations

import shutil
import time

from app.config import SORTIES_DIR, get_reglages


def purger_anciennes_sorties(max_age_heures: int | None = None) -> int:
    """Supprime les dossiers de job plus anciens que le seuil. Renvoie le nombre supprimé."""
    if max_age_heures is None:
        max_age_heures = get_reglages().retention_heures
    if max_age_heures <= 0 or not SORTIES_DIR.exists():
        return 0

    seuil = time.time() - max_age_heures * 3600
    supprimes = 0
    for job in SORTIES_DIR.iterdir():
        try:
            if job.is_dir() and job.stat().st_mtime < seuil:
                shutil.rmtree(job, ignore_errors=True)
                supprimes += 1
        except OSError:
            continue
    return supprimes
