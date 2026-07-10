"""Serveur de PRÉVISUALISATION de l'interface (dev uniquement) : sans authentification,
sur un port dédié, pour vérifier visuellement le design. Ne pas utiliser en production."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["GB_PASSWORD"] = ""
os.environ["GB_PASSWORD_HASH"] = ""

import uvicorn  # noqa: E402

from app.main import app  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8010, log_level="warning")
