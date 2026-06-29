"""Génère une empreinte de mot de passe pour GB_PASSWORD_HASH (mot de passe jamais stocké en clair).

Usage :
    python scripts/hash_password.py            # demande le mot de passe sans l'afficher
    python scripts/hash_password.py "secret"   # ou en argument

Copiez la ligne affichée dans .env :  GB_PASSWORD_HASH=pbkdf2_sha256$...
"""

from __future__ import annotations

import getpass
import sys
from pathlib import Path

# Console Windows (cp1252) : sortie en UTF-8 pour éviter tout plantage d'encodage.
for _flux in (sys.stdout, sys.stderr):
    try:
        _flux.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.securite import hacher  # noqa: E402


def main() -> None:
    mdp = sys.argv[1] if len(sys.argv) > 1 else getpass.getpass("Mot de passe : ")
    if not mdp.strip():
        print("Mot de passe vide — abandon.")
        raise SystemExit(1)
    print("\nÀ coller dans .env :\n")
    print(f"GB_PASSWORD_HASH={hacher(mdp)}\n")


if __name__ == "__main__":
    main()
