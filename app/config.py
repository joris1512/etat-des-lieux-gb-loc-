"""Réglages et chemins du projet — 100% pathlib, cross-platform (Mac/Windows)."""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

VERSION = "2.0.0"

# Racine du projet = dossier parent de `app/`.
# En mode « figé » (.exe PyInstaller --onedir), la racine est le dossier de l'exécutable
# (les données templates/ config/ … y sont livrées à côté, et restent modifiables).
if getattr(sys, "frozen", False):
    # PyInstaller --onedir : les données livrées (--add-data) sont dans le dossier `_internal`
    # exposé via sys._MEIPASS ; ce dossier est réel et modifiable (règles, modèles, runtime).
    RACINE = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    # ⚠️ LES DONNÉES (base clients, documents, clé API) vivent HORS du dossier programme :
    # une réinstallation / mise à jour ne peut ainsi JAMAIS les toucher.
    DONNEES_DIR = Path(os.environ.get("LOCALAPPDATA") or str(RACINE)) / "GB Etats des lieux - donnees"
else:
    RACINE = Path(__file__).resolve().parents[1]
    DONNEES_DIR = RACINE

TEMPLATES_DIR = RACINE / "templates"
CONFIG_CELLULES = RACINE / "config" / "cellules.yaml"
CORRESPONDANCES_CSV = RACINE / "correspondances.csv"
FIXTURES_DIR = RACINE / "fixtures"
RUNTIME_DIR = DONNEES_DIR / "runtime"
SORTIES_DIR = RUNTIME_DIR / "sorties"
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
