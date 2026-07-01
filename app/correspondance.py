"""Normalisation de texte + chargement et application de la table de correspondance."""

from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.config import CORRESPONDANCES_CSV

# Prestations à IGNORER totalement (jamais des états des lieux). Si une ligne d'article
# non reconnue contient l'un de ces mots, on la laisse tomber SANS la signaler comme
# « non reconnue » (ce n'est pas un module, c'est une prestation).
MOTS_PRESTATION = {
    "TRANSPORT",
    "MANUTENTION",
    "ELINGAGE",
    "SUPERPOSITION",
    "DESUPERPOSITION",
    "CONFIGURATION",
    "ASSEMBLAGE",
    "DESASSEMBLAGE",
    "MONTAGE",
    "DEMONTAGE",
    "PRESTATION EXTERIEURE",
    "ESCALIER",
    "RING",
    "CARBURANT",
    "INDEXATION",
    "PIRL",
    "BRANCHEMENT",
    "CLIMATISEUR",
    "LOCATIONS RING",
}


def normaliser(texte: str) -> str:
    """Majuscules, accents retirés, ponctuation -> espaces, espaces normalisés."""
    texte = texte.upper().replace("²", "2")
    # Décompose puis retire les accents (combining marks).
    texte = "".join(c for c in unicodedata.normalize("NFKD", texte) if not unicodedata.combining(c))
    texte = re.sub(r"[^A-Z0-9]+", " ", texte)
    return re.sub(r"\s+", " ", texte).strip()


@dataclass(frozen=True)
class EntreeCorrespondance:
    pattern_norm: str
    modele: str
    categorie: str
    est_bungalow: bool


def _to_bool(val: str) -> bool:
    return val.strip().lower() in {"true", "1", "oui", "yes"}


@lru_cache
def charger_correspondances(chemin: Path | None = None) -> tuple[EntreeCorrespondance, ...]:
    """Charge la table CSV (lignes commençant par `#` ignorées), motifs normalisés."""
    chemin = chemin or CORRESPONDANCES_CSV
    with chemin.open(encoding="utf-8") as f:
        lignes = [ln for ln in f if not ln.lstrip().startswith("#")]
    entrees: list[EntreeCorrespondance] = []
    for row in csv.DictReader(lignes):
        pattern = (row.get("pattern") or "").strip()
        modele = (row.get("modele") or "").strip()
        if not pattern or not modele:
            continue
        entrees.append(
            EntreeCorrespondance(
                pattern_norm=normaliser(pattern),
                modele=modele,
                categorie=(row.get("categorie") or "").strip(),
                est_bungalow=_to_bool(row.get("est_bungalow") or ""),
            )
        )
    # Tri par longueur de motif décroissante : le plus spécifique l'emporte.
    # Départage déterministe (ordre alphabétique du motif) à longueur égale, pour ne pas
    # dépendre de l'ordre des lignes du CSV.
    entrees.sort(key=lambda e: (-len(e.pattern_norm), e.pattern_norm))
    return tuple(entrees)


def trouver_modele(texte_ligne: str, chemin: Path | None = None) -> EntreeCorrespondance | None:
    """Renvoie l'entrée la plus SPÉCIFIQUE dont TOUS les mots-clés figurent dans la ligne.

    Correspondance par **mots entiers** (pas par sous-chaîne) : un motif ne s'applique que si
    chacun de ses mots-clés est présent dans la ligne. Évite les faux positifs (ex. « DOUCHES »
    ne matche pas « 1 DOUCHE » d'un sanitaire mixte). En cas de plusieurs motifs valides, le plus
    spécifique gagne : d'abord le plus grand nombre de mots-clés, puis le motif le plus long.
    """
    tokens = set(normaliser(texte_ligne).split())
    meilleur: EntreeCorrespondance | None = None
    meilleur_score: tuple[int, int] = (0, 0)
    for entree in charger_correspondances(chemin):
        mots = entree.pattern_norm.split()
        if mots and all(m in tokens for m in mots):
            score = (len(mots), len(entree.pattern_norm))
            if score > meilleur_score:
                meilleur, meilleur_score = entree, score
    return meilleur


def est_prestation(texte_ligne: str) -> bool:
    """True si la ligne est une prestation à ignorer (transport, assemblage, etc.)."""
    cible = normaliser(texte_ligne)
    return any(normaliser(mot) in cible for mot in MOTS_PRESTATION)
