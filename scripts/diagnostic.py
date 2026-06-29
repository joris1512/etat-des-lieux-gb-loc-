"""Diagnostic d'installation — à lancer sur le serveur pour vérifier que tout est prêt.

Affiche un rapport clair (OK / À VÉRIFIER / PROBLÈME) : version de Python, dépendances,
clé API, mot de passe, modèles présents, config lisible, port disponible.
Code de sortie 0 si prêt à servir, 1 sinon.

    .venv\\Scripts\\python.exe scripts\\diagnostic.py        (Windows)
    .venv/bin/python scripts/diagnostic.py                   (macOS/Linux)
"""

from __future__ import annotations

import socket
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

OK, ATTENTION, PROBLEME = "  [OK]   ", "  [! ]   ", "  [XX]   "
_souci = False


def ligne(etat: str, message: str) -> None:
    global _souci
    if etat is PROBLEME:
        _souci = True
    print(etat + message)


def verifier_python() -> None:
    v = sys.version_info
    msg = f"Python {v.major}.{v.minor}.{v.micro}"
    if (v.major, v.minor) >= (3, 12):
        ligne(OK, msg)
    else:
        ligne(PROBLEME, msg + " — Python 3.12+ requis.")


def verifier_dependances() -> None:
    requis = {
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "openpyxl": "openpyxl",
        "anthropic": "anthropic",
        "pydantic": "pydantic",
        "pydantic_settings": "pydantic-settings",
        "yaml": "PyYAML",
        "multipart": "python-multipart",
    }
    manquants = []
    for module, pip_nom in requis.items():
        try:
            __import__(module)
        except ImportError:
            manquants.append(pip_nom)
    if manquants:
        ligne(PROBLEME, "Dépendances manquantes : " + ", ".join(manquants) + " (pip install -r requirements.txt)")
    else:
        ligne(OK, f"Dépendances installées ({len(requis)})")


def verifier_reglages() -> None:
    from app.config import get_reglages

    r = get_reglages()
    if r.anthropic_api_key:
        ligne(OK, "Clé API Anthropic présente (extraction de devis active)")
    else:
        ligne(PROBLEME, "ANTHROPIC_API_KEY absente — l'extraction réelle échouera (.env). Le mode Démo reste possible.")

    if r.mot_de_passe:
        ligne(OK, f"Authentification ACTIVÉE (utilisateur « {r.utilisateur} »)")
    else:
        ligne(ATTENTION, "Authentification DÉSACTIVÉE (GB_PASSWORD vide) — appli ouverte. Recommandé de définir GB_PASSWORD.")


def verifier_modeles() -> None:
    from app.modeles import lister_modeles

    data = lister_modeles()
    presents = sum(1 for m in data["attendus"] if m["present"])
    total = len(data["attendus"])
    if data["manquants"] == 0:
        ligne(OK, f"Modèles Excel : {presents}/{total} présents")
    else:
        manquants = [m["nom"] for m in data["attendus"] if not m["present"]]
        ligne(ATTENTION, f"Modèles manquants ({data['manquants']}) : {', '.join(manquants)} — ces états ne seront pas générés.")


def verifier_config() -> None:
    from app.correspondance import charger_correspondances
    from app.remplissage import _config_cellules

    try:
        n = len(charger_correspondances())
        _config_cellules()
        ligne(OK, f"Configuration lisible (correspondances : {n} entrées, cellules OK)")
    except Exception as exc:  # noqa: BLE001
        ligne(PROBLEME, f"Configuration illisible : {exc}")


def verifier_port() -> None:
    from app.config import get_reglages

    r = get_reglages()
    hote = "" if r.host in {"0.0.0.0", ""} else r.host
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((hote, r.port))
        ligne(OK, f"Port {r.port} disponible")
    except OSError:
        ligne(ATTENTION, f"Port {r.port} déjà utilisé — changez GB_PORT ou arrêtez l'autre service.")
    finally:
        s.close()


def main() -> int:
    print("\n=== Diagnostic GB Location — états des lieux ===\n")
    verifier_python()
    verifier_dependances()
    verifier_reglages()
    verifier_modeles()
    verifier_config()
    verifier_port()
    print()
    if _souci:
        print("==> PROBLÈME(S) bloquant(s) détecté(s) : corrigez les lignes [XX] avant de démarrer.\n")
        return 1
    print("==> Prêt à démarrer.  →  scripts/run_prod.bat (ou la tâche de démarrage auto).\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
