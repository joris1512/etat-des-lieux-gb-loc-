"""Réglages et chemins du projet — 100% pathlib, cross-platform (Mac/Windows)."""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

VERSION = "2.7.2"

# Racine du projet = dossier parent de `app/`.
# En mode « figé » (.exe PyInstaller --onedir), la racine est le dossier de l'exécutable
# (les données templates/ config/ … y sont livrées à côté, et restent modifiables).
def _est_reseau(chemin: Path) -> bool:
    """True si `chemin` est sur un partage réseau (UNC ou lecteur mappé distant, ex. P:)."""
    try:
        texte = str(chemin)
        if texte.startswith("\\\\"):  # chemin UNC \\serveur\partage
            return True
        lecteur = os.path.splitdrive(texte)[0]
        if lecteur and os.name == "nt":
            import ctypes

            return ctypes.windll.kernel32.GetDriveTypeW(lecteur + "\\") == 4  # DRIVE_REMOTE
    except Exception:  # noqa: BLE001 — en cas de doute, on suppose « local »
        pass
    return False


# Emplacement de l'ancienne installation (données dans %LOCALAPPDATA%) — sert à la MIGRATION
# automatique vers le dossier partagé sur le serveur (voir main.migrer_donnees_programme).
ANCIEN_DONNEES_DIR: Path | None = None

if getattr(sys, "frozen", False):
    # PyInstaller --onedir : les données livrées (--add-data) sont dans le dossier `_internal`
    # exposé via sys._MEIPASS ; ce dossier est réel et modifiable (règles, modèles, runtime).
    RACINE = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    # LES DONNÉES (base clients, documents) vivent HORS du dossier programme, dans un dossier
    # PARTAGÉ posé À CÔTÉ du programme (sur le serveur) : tous les postes qui lancent le même
    # exécutable partagent ainsi la MÊME base (comptes, clients, historique). Le chemin est
    # relatif à l'exécutable → il suit le programme quel que soit le lecteur réseau mappé.
    _defaut = Path(sys.executable).resolve().parent.parent / "GB Etats des lieux - donnees"
    DONNEES_DIR = Path(os.environ.get("GB_DONNEES_DIR") or _defaut)
    ANCIEN_DONNEES_DIR = Path(os.environ.get("LOCALAPPDATA") or str(RACINE)) / "GB Etats des lieux - donnees"
else:
    RACINE = Path(__file__).resolve().parents[1]
    # Mode source (non figé) : par défaut les données vivent dans le dépôt. Mais si l'app est
    # LANCÉE DEPUIS LES SOURCES sur un poste (contournement antivirus : pas d'exe à compiler),
    # `GB_DONNEES_DIR` permet de pointer vers le dossier PARTAGÉ du serveur (mêmes comptes/clients).
    DONNEES_DIR = Path(os.environ["GB_DONNEES_DIR"]) if os.environ.get("GB_DONNEES_DIR") else RACINE

# La base est-elle sur un partage réseau ? (→ mode journal SQLite compatible SMB dans db.py)
DONNEES_RESEAU = _est_reseau(DONNEES_DIR)

TEMPLATES_DIR = RACINE / "templates"
CONFIG_CELLULES = RACINE / "config" / "cellules.yaml"
CORRESPONDANCES_CSV = RACINE / "correspondances.csv"
FIXTURES_DIR = RACINE / "fixtures"
RUNTIME_DIR = DONNEES_DIR / "runtime"
SORTIES_DIR = RUNTIME_DIR / "sorties"
DOCUMENTS_DIR = RUNTIME_DIR / "documents"  # pièces jointes aux chantiers (scans, PDF, photos…)
HTML_DIR = RACINE / "app" / "templates_html"
STATIC_DIR = RACINE / "app" / "static"


class Reglages(BaseSettings):
    """Variables d'environnement (chargées depuis `.env`)."""

    anthropic_api_key: str | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    modele_extraction: str = Field(default="claude-opus-4-8", validation_alias="GB_MODEL")

    # Authentification (optionnelle). Activée si GB_PASSWORD **ou** GB_PASSWORD_HASH est défini.
    # Préférez GB_PASSWORD_HASH (mot de passe haché, voir scripts/hash_password.py) en production.
    utilisateur: str = Field(default="gb", validation_alias="GB_USER")
    mot_de_passe: str | None = Field(default=None, validation_alias="GB_PASSWORD")
    mot_de_passe_hash: str | None = Field(default=None, validation_alias="GB_PASSWORD_HASH")

    # Rétention des fichiers générés, en heures (0 = jamais purger).
    # Défaut élevé (≈ 1 an) pour que l'historique reste re-téléchargeable.
    retention_heures: int = Field(default=8760, validation_alias="GB_RETENTION_HEURES")

    # Hôte / port (utilisés par les scripts de lancement).
    host: str = Field(default="127.0.0.1", validation_alias="GB_HOST")
    port: int = Field(default=8000, validation_alias="GB_PORT")

    # Derrière un proxy de confiance (Caddy sur le serveur, tunnel Cloudflare) : lire l'IP
    # réelle du client dans CF-Connecting-IP / X-Forwarded-For (anti-force-brute, journal).
    # NE PAS activer quand l'app est exposée en direct (l'en-tête serait falsifiable).
    proxy_confiance: bool = Field(default=False, validation_alias="GB_PROXY_CONFIANCE")

    @field_validator("mot_de_passe", "mot_de_passe_hash", mode="before")
    @classmethod
    def _normaliser_secret(cls, v: object) -> str | None:
        """Une valeur vide ou en blanc équivaut à 'non défini' (évite une activation ambiguë)."""
        if v is None:
            return None
        texte = str(v).strip()
        return texte or None

    model_config = SettingsConfigDict(
        # Le .env du dossier de DONNÉES (dernier de la liste) prime sur celui du programme :
        # la clé API survit ainsi aux réinstallations.
        env_file=(str(RACINE / ".env"), str(DONNEES_DIR / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_reglages() -> Reglages:
    """Réglages mis en cache (chargés une seule fois)."""
    return Reglages()
