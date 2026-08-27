"""Sauvegarde automatique de la base de connaissance + documents (une par jour, 30 conservées).

À chaque démarrage de l'application, si aucune sauvegarde n'existe pour aujourd'hui, la base
SQLite (copie cohérente via l'API de backup, même base ouverte) ET les documents de chantier
(photos, scans, xlsx signés) sont zippés dans runtime/sauvegardes/. Une COPIE est ensuite faite
HORS du serveur si un emplacement externe est disponible (OneDrive du poste, ou le chemin
`GB_SAUVEGARDE_EXTERNE`), pour ne pas dépendre d'un seul endroit.

Restauration : dézipper le .zip → remplacer runtime/gb.db (application arrêtée). Les documents
sont rangés sous « documents/ » dans le zip.
"""

from __future__ import annotations

import logging
import os
import shutil
import sqlite3
import zipfile
from datetime import date
from pathlib import Path

from app import db
from app.config import DOCUMENTS_DIR, RUNTIME_DIR

logger = logging.getLogger("uvicorn.error")

DOSSIER = RUNTIME_DIR / "sauvegardes"
A_CONSERVER = 30  # ~1 mois de sauvegardes quotidiennes


def _dossier_externe() -> Path | None:
    """Emplacement de COPIE hors du serveur (offsite), si disponible.

    Priorité : `GB_SAUVEGARDE_EXTERNE` (chemin explicite : autre serveur, disque, cloud
    synchronisé…) ; à défaut, le dossier OneDrive du poste. None = pas de copie externe.
    """
    explicite = os.environ.get("GB_SAUVEGARDE_EXTERNE")
    if explicite and explicite.strip():
        return Path(explicite.strip())
    onedrive = os.environ.get("OneDrive") or os.environ.get("OneDriveCommercial")
    if onedrive:
        return Path(onedrive) / "Sauvegardes GB Etats des lieux"
    return None


def _rotation(dossier: Path, garder: int = A_CONSERVER) -> None:
    """Ne conserve que les `garder` sauvegardes les plus récentes dans `dossier`."""
    sauvegardes = sorted(dossier.glob("gb-*.zip"))
    for ancienne in sauvegardes[:-garder]:
        try:
            ancienne.unlink(missing_ok=True)
        except OSError:
            pass


def sauvegarder_quotidienne() -> bool:
    """Crée la sauvegarde du jour si absente. Renvoie True si une sauvegarde a été créée."""
    if not db.DB_PATH.exists():
        return False
    cible = DOSSIER / f"gb-{date.today().isoformat()}.zip"
    if cible.exists():
        return False
    DOSSIER.mkdir(parents=True, exist_ok=True)

    # Copie cohérente de la base via l'API de backup SQLite (fonctionne même base utilisée).
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
            # Documents de chantier (photos, scans, xlsx signés) : tout le dossier, s'il existe.
            if DOCUMENTS_DIR.exists():
                for chemin in DOCUMENTS_DIR.rglob("*"):
                    if chemin.is_file():
                        arc = Path("documents") / chemin.relative_to(DOCUMENTS_DIR)
                        zf.write(chemin, arcname=str(arc))
    finally:
        tmp.unlink(missing_ok=True)

    _rotation(DOSSIER)

    # Copie HORS du serveur (offsite) — best-effort : ne doit JAMAIS bloquer l'application.
    externe = _dossier_externe()
    if externe:
        try:
            externe.mkdir(parents=True, exist_ok=True)
            shutil.copy2(cible, externe / cible.name)
            _rotation(externe)
            logger.info("Sauvegarde copiée hors du serveur : %s", externe / cible.name)
        except Exception as exc:  # noqa: BLE001 — une copie externe impossible ne bloque pas l'app
            logger.warning("Copie de sauvegarde externe impossible (%s) : %s", externe, exc)

    logger.info("Sauvegarde quotidienne créée : %s", cible.name)
    return True
