"""Détection de la fonction d'un bungalow à partir du « bloc » du devis.

Sur les modèles bungalow, une ligne propose « BUREAU / SALLE DE REUNION / VESTIAIRE / REFECTOIRE ».
À partir du bloc fonctionnel lu sur le devis (ex. « 2 BUREAUX INDEPENDANTS », « VESTIAIRE HOMMES »),
on déduit la fonction canonique à reporter sur cette ligne. La table est dans
config/cellules.yaml (section `fonctions`) pour rester ajustable sans toucher au code.
"""

from __future__ import annotations

from functools import lru_cache

import yaml

from app.config import CONFIG_CELLULES
from app.correspondance import normaliser


@lru_cache
def _table_fonctions() -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Charge la table (texte canonique, motifs normalisés) depuis cellules.yaml, dans l'ordre."""
    cfg = yaml.safe_load(CONFIG_CELLULES.read_text(encoding="utf-8")) or {}
    table: list[tuple[str, tuple[str, ...]]] = []
    for entree in cfg.get("fonctions", []) or []:
        texte = (entree.get("texte") or "").strip()
        motifs = tuple(normaliser(m) for m in (entree.get("motifs") or []) if m and str(m).strip())
        if texte and motifs:
            table.append((texte, motifs))
    return tuple(table)


def detecter_fonction(bloc: str | None) -> str | None:
    """Renvoie la fonction canonique déduite du bloc, ou None si indéterminée.

    Le 1er motif trouvé (dans l'ordre de la table) gagne : l'ordre fixe donc la priorité.
    """
    if not bloc:
        return None
    cible = normaliser(bloc)
    for texte, motifs in _table_fonctions():
        if any(motif and motif in cible for motif in motifs):
            return texte
    return None
