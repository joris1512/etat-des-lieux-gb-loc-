"""Gestion des modèles Excel depuis l'application : lister, téléverser (remplacer), supprimer.

Permet de mettre à jour un modèle sans accès au serveur : on dépose le .xlsx via la page web,
il atterrit dans templates/ et est pris en compte immédiatement (les modèles sont relus à chaque
génération). Validation stricte du nom et du contenu (vrai classeur Excel).
"""

from __future__ import annotations

import io
import zipfile
from datetime import datetime
from pathlib import Path

import yaml
from openpyxl import load_workbook

from app.config import CONFIG_CELLULES, TEMPLATES_DIR
from app.correspondance import charger_correspondances

TAILLE_MAX = 20 * 1024 * 1024  # 20 Mo (fichier compressé)
TAILLE_DECOMPRESSEE_MAX = 150 * 1024 * 1024  # 150 Mo (XML décompressé) — anti zip-bomb
RATIO_MAX = 200  # ratio de décompression max toléré


def modeles_attendus() -> list[str]:
    """Noms de fichiers attendus = modèles de la table de correspondance + modèle assemblé."""
    noms = {e.modele for e in charger_correspondances()}
    cfg = yaml.safe_load(CONFIG_CELLULES.read_text(encoding="utf-8"))
    noms.add(cfg.get("modele_assemble", "bungalow_assemble.xlsx"))
    return sorted(noms)


def _info(chemin: Path | None, nom: str) -> dict:
    if chemin is None:
        return {"nom": nom, "present": False, "taille": None, "modifie": None}
    st = chemin.stat()
    return {
        "nom": nom,
        "present": True,
        "taille": st.st_size,
        "modifie": datetime.fromtimestamp(st.st_mtime).strftime("%d/%m/%Y %H:%M"),
    }


def lister_modeles() -> dict:
    """Renvoie l'état des modèles : attendus (présents/manquants) + fichiers supplémentaires."""
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    presents = {
        p.name: p for p in TEMPLATES_DIR.glob("*.xlsx") if not p.name.startswith("~$")
    }
    attendus = modeles_attendus()
    attendus_info = [_info(presents.get(n), n) for n in attendus]
    supplementaires = [_info(presents[n], n) for n in sorted(set(presents) - set(attendus))]
    manquants = sum(1 for m in attendus_info if not m["present"])
    return {
        "attendus": attendus_info,
        "supplementaires": supplementaires,
        "manquants": manquants,
    }


def _valider_nom(nom: str) -> str:
    """Réduit au nom de base, exige .xlsx, refuse toute tentative d'évasion de chemin."""
    # Path(nom).name retire tout dossier ; on traite aussi les séparateurs Windows.
    base = Path(nom.replace("\\", "/")).name
    if not base.lower().endswith(".xlsx"):
        raise ValueError("Le fichier doit être un .xlsx.")
    if base.startswith("~$") or base in {"", ".", ".."}:
        raise ValueError("Nom de fichier invalide.")
    return base


def _verifier_zip_raisonnable(contenu: bytes) -> None:
    """Borne la taille DÉCOMPRESSÉE d'un .xlsx (zip) avant de le confier à openpyxl (anti zip-bomb)."""
    try:
        with zipfile.ZipFile(io.BytesIO(contenu)) as zf:
            decompresse = sum(info.file_size for info in zf.infolist())
    except zipfile.BadZipFile as exc:
        raise ValueError("Fichier Excel illisible : archive invalide.") from exc
    if decompresse > TAILLE_DECOMPRESSEE_MAX:
        raise ValueError("Modèle trop volumineux une fois décompressé.")
    if len(contenu) and decompresse / len(contenu) > RATIO_MAX:
        raise ValueError("Modèle suspect (ratio de compression anormal).")


def enregistrer_modele(nom: str, contenu: bytes) -> str:
    """Valide puis enregistre (ou remplace) un modèle dans templates/. Renvoie le nom retenu."""
    base = _valider_nom(nom)
    if not contenu:
        raise ValueError("Fichier vide.")
    if len(contenu) > TAILLE_MAX:
        raise ValueError("Fichier trop volumineux (max 20 Mo).")
    _verifier_zip_raisonnable(contenu)
    try:
        load_workbook(io.BytesIO(contenu), read_only=True).close()
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Fichier Excel illisible : {exc}") from exc
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    (TEMPLATES_DIR / base).write_bytes(contenu)
    return base


def supprimer_modele(nom: str) -> None:
    """Supprime un modèle de templates/ (avec garde-fou de chemin)."""
    base = _valider_nom(nom)
    cible = (TEMPLATES_DIR / base).resolve()
    if cible.parent != TEMPLATES_DIR.resolve():
        raise ValueError("Chemin invalide.")
    if cible.exists():
        cible.unlink()
