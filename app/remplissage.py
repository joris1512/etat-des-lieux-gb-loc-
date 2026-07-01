"""Remplissage des modèles Excel — en-tête + fonction + mobilier.

On écrit UNIQUEMENT les cellules prévues par config/cellules.yaml via `app.patch_xlsx`, qui
modifie le XML de la feuille ciblée **en préservant tout le reste du classeur** : logo GB,
dessins en perspective, mise en forme, autres onglets. (openpyxl, lui, perd images et dessins
à l'enregistrement — d'où ce moteur dédié.) On ne touche jamais aux champs d'état réel,
réserves ou signatures.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from app import patch_xlsx
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
    }
    # En-tête, format d'en-tête et mobilier : une surcharge explicite (même vide) REMPLACE le
    # défaut (les vrais modèles ont leurs propres cellules, à ne pas fusionner avec le défaut).
    resolu["entete"] = (
        surcharge["entete"] if "entete" in surcharge else (defaut.get("entete") or {})
    )
    resolu["entete_format"] = (
        surcharge["entete_format"]
        if "entete_format" in surcharge
        else (defaut.get("entete_format") or {})
    )
    resolu["fonctions_cellules"] = (
        surcharge.get("fonctions_cellules") or defaut.get("fonctions_cellules") or {}
    )
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
    a_ecrire: dict[str, object] = {}

    # --- En-tête ---
    valeurs_entete = {
        "client": entete.client,
        "titre_chantier": entete.titre_chantier,
        "adresse": entete.adresse,
        "code_postal": entete.code_postal,
        "ville": entete.ville,
        "numero_offre": entete.numero_offre,
    }
    formats = cfg.get("entete_format") or {}
    for champ, cellule in (cfg.get("entete") or {}).items():
        valeur = valeurs_entete.get(champ)
        if valeur and cellule:
            # Sur les vrais modèles, le libellé fait partie de la cellule (ex. « Client : … ») :
            # un gabarit « Client : {valeur} » reconstitue le libellé + la valeur.
            gabarit = formats.get(champ)
            a_ecrire[cellule] = gabarit.format(valeur=valeur) if gabarit else valeur

    # --- Fonction du bungalow ---
    # On REMPLACE la ligne « BUREAU / SALLE DE REUNION / VESTIAIRE / REFECTOIRE » par la
    # fonction retenue (ex. « VESTIAIRE »). Rien n'est écrit si la fonction est indéterminée.
    cellule_fonction = cfg.get("fonction")
    if cellule_fonction and etat.fonction:
        a_ecrire[cellule_fonction] = etat.fonction

    # Modèles à 4 cases séparées (réunion / vestiaire / bureau / réfectoire) : on marque la bonne.
    cells_fonction = cfg.get("fonctions_cellules") or {}
    if cells_fonction and etat.fonction and etat.fonction in cells_fonction:
        a_ecrire[cells_fonction[etat.fonction]] = f"» {etat.fonction} «"

    # --- Mobilier (somme par cellule) ---
    # Seulement si le modèle a des CASES quantité mobilier. Les vrais modèles n'en ont pas :
    # le mobilier y est matérialisé par le CHOIX du modèle « avec mobilier » (pas d'avertissement).
    table_mobilier = cfg.get("mobilier") or {}
    non_mappes: list[str] = []
    if table_mobilier:
        sommes: dict[str, int] = {}
        for item in etat.mobilier:
            cellule = _cellule_mobilier(item.designation, table_mobilier)
            if cellule:
                sommes[cellule] = sommes.get(cellule, 0) + item.quantite
            else:
                non_mappes.append(item.designation)
        a_ecrire.update(sommes)

    patch_xlsx.ecrire_cellules(modele_path, sortie_path, cfg.get("feuille"), a_ecrire)
    return non_mappes
