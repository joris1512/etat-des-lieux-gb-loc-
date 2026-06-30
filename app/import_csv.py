"""Import d'une base clients depuis un CSV (export CRM / tableur).

Détecte l'encodage et le séparateur, mappe des en-têtes de colonnes courants (souples) vers les
champs de la base, et renvoie une liste de clients prêts à enrichir la base de connaissance.
On ne devine rien d'ambigu : seules les colonnes reconnues sont importées.
"""

from __future__ import annotations

import csv
import io

from app.correspondance import normaliser

# Pour chaque champ cible, les en-têtes acceptés (normalisés), par ordre de priorité.
_COLONNES: dict[str, list[str]] = {
    "raison_sociale": ["RAISON SOCIALE", "RAISON", "NOM CLIENT", "SOCIETE", "NOM"],
    "numero_client": ["N CLIENT", "NUMERO CLIENT", "NO CLIENT", "CODE CLIENT", "CLIENT"],
    "commercial": ["CIAL", "COMMERCIAL"],
    "interlocuteur": ["INTERLOCUTEUR", "CONTACT"],
    "ville": ["VILLE", "COMMUNE"],
    "code_postal": ["CODE POSTAL", "CP"],
}


def _decoder(contenu: bytes) -> str:
    """Décode le CSV en essayant les encodages courants des exports français."""
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return contenu.decode(enc)
        except UnicodeDecodeError:
            continue
    return contenu.decode("utf-8", errors="replace")


def _separateur(premiere_ligne: str) -> str:
    """Séparateur le plus probable parmi ; , et tabulation."""
    return max(";", ",", "\t", key=premiere_ligne.count)


def parser(contenu: bytes) -> list[dict]:
    """Renvoie la liste des clients lus dans le CSV (champs reconnus uniquement)."""
    texte = _decoder(contenu)
    if not texte.strip():
        return []
    sep = _separateur(texte.splitlines()[0])
    lecteur = csv.DictReader(io.StringIO(texte), delimiter=sep)
    entetes = {normaliser(h): h for h in (lecteur.fieldnames or []) if h and h.strip()}

    mapping: dict[str, str] = {}
    for champ, candidats in _COLONNES.items():
        for cand in candidats:
            if cand in entetes:
                mapping[champ] = entetes[cand]
                break
    if "raison_sociale" not in mapping and "numero_client" not in mapping:
        raise ValueError(
            "Aucune colonne reconnue (attendu au moins « Raison sociale » ou « Client »)."
        )

    lignes: list[dict] = []
    for row in lecteur:
        vals = {champ: (row.get(col) or "").strip() for champ, col in mapping.items()}
        if not vals.get("raison_sociale") and not vals.get("numero_client"):
            continue
        lignes.append(
            {
                "raison_sociale": vals.get("raison_sociale", ""),
                "numero_client": vals.get("numero_client") or None,
                "commercial": vals.get("commercial") or None,
                "interlocuteur": vals.get("interlocuteur") or None,
                "ville": vals.get("ville") or None,
                "code_postal": vals.get("code_postal") or None,
            }
        )
    return lignes
