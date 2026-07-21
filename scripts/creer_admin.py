"""Crée (ou réinitialise) un compte administrateur — utilisé par l'installeur VPS pour garantir
qu'aucune mise en ligne publique ne reste SANS authentification.

Usage :
    python scripts/creer_admin.py --verifier          # code retour 0 si un admin actif existe, 1 sinon
    python scripts/creer_admin.py <identifiant> <mot_de_passe>
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# La console Windows (cp1252) ne peut pas afficter certains caractères : on force l'UTF-8.
for flux in (sys.stdout, sys.stderr):
    try:
        flux.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

from app import db  # noqa: E402
from app.securite import hacher  # noqa: E402


def main() -> int:
    db.init_db()
    if "--verifier" in sys.argv:
        return 0 if db.utilisateurs_actifs_existent() else 1
    if len(sys.argv) < 3:
        print("Usage : creer_admin.py <identifiant> <mot_de_passe>")
        return 2
    identifiant, mot_de_passe = sys.argv[1].strip(), sys.argv[2]
    if len(mot_de_passe) < 8:
        print("Mot de passe trop court (8 caractères minimum).")
        return 2
    existant = db.lire_utilisateur(identifiant)
    if existant:
        db.modifier_utilisateur(existant["id"], hash_=hacher(mot_de_passe))
        print(f"Mot de passe du compte administrateur « {identifiant} » réinitialisé.")
    else:
        db.creer_utilisateur(identifiant, identifiant, hacher(mot_de_passe), "admin")
        print(f"Compte administrateur « {identifiant} » créé.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
