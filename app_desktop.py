"""GB — États des lieux : application de bureau (fenêtre native, sans navigateur).

Architecture robuste : le serveur tourne dans SON PROPRE PROCESSUS (thread principal → uvicorn OK
sous Windows), la fenêtre WebView2 dans le processus lanceur. Fonctionne lancé par Python
(`python app_desktop.py`) comme empaqueté en .exe (PyInstaller --onedir).

- Processus « serveur » : détecté via la variable d'environnement GB_SERVEUR=1.
- Processus « lanceur » : démarre le serveur (s'il n'écoute pas déjà) puis ouvre la fenêtre.
"""

from __future__ import annotations

import multiprocessing
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

HOTE = "127.0.0.1"
PORT = int(os.environ.get("GB_PORT", "8000"))


def _journaliser_erreur(exc: BaseException) -> None:
    """Écrit la trace d'erreur à côté de l'exe/script (le mode fenêtre n'a pas de console)."""
    import traceback

    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
    try:
        (base / "gb_erreur.log").write_text(traceback.format_exc(), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def _serveur_repond() -> bool:
    with socket.socket() as s:
        s.settimeout(0.4)
        return s.connect_ex((HOTE, PORT)) == 0


def _run_serveur() -> None:
    """Lance uvicorn dans le thread principal de CE processus (appli de bureau : sans auth, local)."""
    try:
        import uvicorn

        from app.main import app

        uvicorn.run(app, host=HOTE, port=PORT, log_level="warning")
    except BaseException as exc:  # noqa: BLE001
        _journaliser_erreur(exc)
        raise


def _lancer_serveur_process() -> None:
    """Démarre le serveur dans un processus séparé, fenêtre cachée."""
    env = os.environ.copy()
    env["GB_SERVEUR"] = "1"
    env["GB_PASSWORD"] = ""  # appli de bureau locale : pas d'authentification
    env.pop("GB_PASSWORD_HASH", None)
    env["GB_HOST"] = HOTE
    env["GB_PORT"] = str(PORT)
    args = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, os.path.abspath(__file__)]
    flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
    subprocess.Popen(args, env=env, creationflags=flags, close_fds=True)


def main() -> int:
    # En .exe « fenêtre » (windowed), sys.stdout/stderr valent None : uvicorn appelle
    # sys.stdout.isatty() et plante. On fournit un flux neutre pour éviter tout crash.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115

    # Mode « serveur » (processus enfant) : on sert et on bloque.
    if os.environ.get("GB_SERVEUR") == "1":
        _run_serveur()
        return 0

    # Mode « lanceur » : démarre le serveur si besoin, puis ouvre la fenêtre.
    if not _serveur_repond():
        _lancer_serveur_process()
        for _ in range(80):  # ~20 s max
            if _serveur_repond():
                break
            time.sleep(0.25)

    import webview

    # Sans ce réglage, la WebView IGNORE les clics de téléchargement (xlsx/zip) sans message.
    try:
        webview.settings["ALLOW_DOWNLOADS"] = True
    except (AttributeError, KeyError, TypeError):
        pass

    webview.create_window(
        "GB — États des lieux", f"http://{HOTE}:{PORT}", width=1320, height=880, min_size=(1000, 700)
    )
    webview.start()
    return 0


if __name__ == "__main__":
    multiprocessing.freeze_support()  # indispensable pour un .exe figé (évite les relances en boucle)
    sys.exit(main())
