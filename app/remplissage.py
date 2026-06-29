"""Remplissage des modèles Excel via openpyxl — en-tête + quantités de mobilier.

On ouvre le modèle, on écrit UNIQUEMENT les cellules d'en-tête et de mobilier prévues par
config/cellules.yaml, puis on enregistre une copie. La mise en forme du modèle est préservée
(openpyxl conserve styles, fusions, largeurs). On ne touche JAMAIS aux champs d'état réel,
réserves, signatures, ni aux cases de fonction (vestiaire/réfectoire/…).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from openpyxl import load_workbook

from app.config import CONFIG_CELLULES
from app.correspondance import normaliser
from app.models import EnteteDevis, EtatDesLieux


@lru_cache
def _config_cellules() -> dict:
    return yaml.safe_load(CONFIG_CELLULES.read_text(encoding="utf-8"))


def _cfg_modele(modele: str) -> dict:
    """Config résolue pour un modèle : défaut + surcharges éventuelles."""
    cfg = _config_cellules()
    defaut = cfg.get("defaut", {}) or {}
    surcharge = (cfg.get("modeles", {}) or {}).get(modele, {}) or {}
    resolu = {
        "feuille": surcharge.get("feuille", defaut.get("feuille")),
        "fonction": surcharge.get("fonction", defaut.get("fonction")),
        "entete": {**(defaut.get("entete") or {}), **(surcharge.get("entete") or {})},
    }
    # Pour le mobilier, une surcharge explicite (même vide) REMPLACE le défaut.
    resolu["mobilier"] = (
        surcharge["mobilier"] if "mobilier" in surcharge else (defaut.get("mobilier") or {})
    )
    return resolu


def _cellule_mobilier(designation: str, table: dict[str, str]) -> str | None:
    """Trouve la cellule pour une désignation via mot-clé (le plus long qui correspond gagne)."""
    cible = normaliser(designation)
    candidats = sorted(table.items(), key=lambda kv: len(normaliser(kv[0])), reverse=True)
    for mot, cellule in candidats:
        if normaliser(mot) in cible:
            return cellule
    return None


def remplir_etat(
    modele_path: Path,
    sortie_path: Path,
    entete: EnteteDevis,
    etat: EtatDesLieux,
) -> list[str]:
    """Remplit un modèle et l'enregistre. Renvoie la liste des désignations non mappées."""
    cfg = _cfg_modele(etat.modele)
    wb = load_workbook(modele_path)
    feuille = cfg.get("feuille")
    if feuille:
        if feuille not in wb.sheetnames:
            raise ValueError(f"Feuille « {feuille} » absente du modèle {etat.modele}.")
        ws = wb[feuille]
    else:
        ws = wb.active

    # --- En-tête ---
    valeurs_entete = {
        "client": entete.client,
        "titre_chantier": entete.titre_chantier,
        "adresse": entete.adresse,
        "code_postal": entete.code_postal,
        "ville": entete.ville,
        "numero_offre": entete.numero_offre,
    }
    for champ, cellule in (cfg.get("entete") or {}).items():
        valeur = valeurs_entete.get(champ)
        if valeur and cellule:
            ws[cellule] = valeur

    # --- Fonction du bungalow ---
    # On REMPLACE la ligne « BUREAU / SALLE DE REUNION / VESTIAIRE / REFECTOIRE » par la
    # fonction retenue (ex. « VESTIAIRE »). Rien n'est écrit si la fonction est indéterminée
    # (le modèle garde alors sa ligne d'origine, à renseigner à la main).
    cellule_fonction = cfg.get("fonction")
    if cellule_fonction and etat.fonction:
        ws[cellule_fonction] = etat.fonction

    # --- Mobilier (somme par cellule) ---
    table_mobilier = cfg.get("mobilier") or {}
    sommes: dict[str, int] = {}
    non_mappes: list[str] = []
    for item in etat.mobilier:
        cellule = _cellule_mobilier(item.designation, table_mobilier)
        if cellule:
            sommes[cellule] = sommes.get(cellule, 0) + item.quantite
        else:
            non_mappes.append(item.designation)
    for cellule, qte in sommes.items():
        ws[cellule] = qte

    sortie_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(sortie_path)
    return non_mappes
