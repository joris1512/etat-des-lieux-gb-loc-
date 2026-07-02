"""GB — États des lieux : lancement en application de bureau (fenêtre native, sans navigateur).

Démarre le serveur local (s'il n'est pas déjà lancé) puis ouvre une fenêtre WebView2.
Fonctionne aussi bien lancé par Python (`python app_desktop.py`) qu'empaqueté en .exe (PyInstaller).
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time

HOTE = "127.0.0.1"
PORT = 8000


def _serveur_repond() -> bool:
    with socket.socket() as s:
        s.settimeout(0.4)
        return s.connect_ex((HOTE, PORT)) == 0


def _demarrer_serveur() -> None:
    """Serveur embarqué : appli de bureau locale -> pas d'authentification, écoute locale."""
    os.environ["GB_PASSWORD"] = ""
    os.environ.pop("GB_PASSWORD_HASH", None)
    os.environ["GB_HOST"] = HOTE
    os.environ["GB_PORT"] = str(PORT)
    # Import tardif (après config d'environnement) pour que les réglages soient pris en compte.
    import uvicorn

    from app.main import app

    uvicorn.run(app, host=HOTE, port=PORT, log_level="warning")


def main() -> None:
    if not _serveur_repond():
        threading.Thread(target=_demarrer_serveur, daemon=True).start()
        for _ in range(80):  # ~20 s max d'attente du démarrage
            if _serveur_repond():
                break
            time.sleep(0.25)

    import webview

    webview.create_window(
        "GB — États des lieux", f"http://{HOTE}:{PORT}", width=1320, height=880, min_size=(1000, 700)
    )
    webview.start()


if __name__ == "__main__":
    sys.exit(main())
