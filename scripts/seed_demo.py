"""Pré-remplit la base avec le 1er dossier client (devis EIFFAGE), pour une démonstration.

À lancer UNE FOIS après l'installation :
    .venv/bin/python scripts/seed_demo.py        (macOS/Linux)
    .venv\\Scripts\\python.exe scripts\\seed_demo.py   (Windows)

Crée le client EIFFAGE, son chantier, son devis et 17 états des lieux téléchargeables.
La reconnaissance par n° client évite les doublons si on relance.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db  # noqa: E402
from app.generation import generer  # noqa: E402


def main() -> None:
    db.init_db()
    rapport, _ = generer(None, utiliser_fixture=True)
    dash = db.dashboard()
    print(f"\n✔ Dossier EIFFAGE créé : {len(rapport.fichiers)} états des lieux.")
    print(
        f"  Base : {dash['nb_clients']} client(s) · {dash['nb_devis']} devis · "
        f"{dash['total_etats']} états."
    )
    print("\nLancez l'appli puis ouvrez : Clients → EIFFAGE → chantier (devis, documents, historique).\n")


if __name__ == "__main__":
    main()
