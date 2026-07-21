"""Prévisualisation de la page de connexion : lance l'app avec une auth de démo (port 8020).

Usage (via .claude/launch.json « app-auth ») — n'écrit rien dans les comptes : l'auth est
activée par GB_PASSWORD (compte .env de secours), la base de dev n'est pas modifiée.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("GB_PASSWORD", "demo-preview")

import uvicorn  # noqa: E402

from app.main import app  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8020, log_level="warning")
