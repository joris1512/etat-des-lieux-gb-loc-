"""Marquage des états des lieux selon le devis : « garder le bon, effacer les autres ».

Les libellés sont repérés par leur TEXTE (leurs positions varient d'un modèle à l'autre) :
- R5 — fonction du bungalow : garder BUREAU / VESTIAIRE / REFECTOIRE / SALLE DE REUNION retenu,
  effacer les autres cases de fonction.
- R7 / R8 — OUI/NON (climatisé, élingage point bas) : effacer l'option non applicable dans la cellule.
- R1 — choix de l'onglet du modèle DOUCHES selon le nombre de douches.

Chaque fonction `edits_*` renvoie un dict {coordonnée: nouvelle_valeur} à écrire ensuite via
`patch_xlsx` (qui préserve le logo et les perspectives du modèle). `None` = effacer la cellule.
"""

from __future__ import annotations

import re

from app.correspondance import normaliser

# Fonctions possibles d'un bungalow (le devis n'en retient qu'une).
FONCTIONS = ("BUREAU", "VESTIAIRE", "REFECTOIRE", "SALLE DE REUNION")


def _fonction_canonique(txt_norm: str) -> str | None:
    """Fonction canonique si la cellule est un libellé de fonction (gère la faute « VESTIARE »)."""
    if txt_norm in ("VESTIAIRE", "VESTIARE"):
        return "VESTIAIRE"
    return txt_norm if txt_norm in FONCTIONS else None


def edits_fonction(ws, fonction: str | None) -> dict[str, None]:
    """R5 : cellules des fonctions NON retenues, à effacer.

    Sécurité : on n'efface les autres fonctions QUE si la fonction retenue existe bien dans le
    modèle (sinon on ne touche à rien — évite d'effacer TOUTES les fonctions par erreur).
    """
    if not fonction:
        return {}
    garder = "VESTIAIRE" if normaliser(fonction) in ("VESTIAIRE", "VESTIARE") else normaliser(fonction)
    cellules: list[tuple[str, str]] = []  # (coordonnée, fonction canonique)
    for row in ws.iter_rows():
        for c in row:
            if c.value is None:
                continue
            canon = _fonction_canonique(normaliser(str(c.value)))
            if canon:
                cellules.append((c.coordinate, canon))
    if not any(canon == garder for _, canon in cellules):
        return {}  # fonction retenue absente de ce modèle -> ne rien effacer
    return {coord: None for coord, canon in cellules if canon != garder}


def edits_oui_non(ws, prefixe: str, oui: bool) -> dict[str, str]:
    """R7/R8 : dans la cellule « <prefixe> … OUI … NON », efface l'option non applicable.

    Ex. « CLIMATISE :   OUI   NON » + oui=True -> « CLIMATISE : OUI ». Dict vide si le libellé est
    absent du modèle (ex. élingage sur un 8 m²) : rien à marquer.
    """
    cible = normaliser(prefixe)
    for row in ws.iter_rows():
        for c in row:
            if c.value is None:
                continue
            txt = str(c.value)
            haut = txt.upper()
            if cible in normaliser(txt) and ("OUI" in haut or "NON" in haut):
                a_retirer = "NON" if oui else "OUI"
                nouveau = re.sub(rf"\b{a_retirer}\b", "", txt, flags=re.IGNORECASE)
                nouveau = re.sub(r"[ \t]{2,}", " ", nouveau).rstrip()
                return {c.coordinate: nouveau}
    return {}


def edits_doses(ws, nombre: int) -> dict[str, str]:
    """R3 : écrit le nombre de doses dans la cellule « DOSES SUPPLEMENTAIRES » (« … : N »).

    Dict vide si le libellé est absent (modèle sans doses) ou si nombre <= 0.
    """
    if not nombre or nombre <= 0:
        return {}
    for row in ws.iter_rows():
        for c in row:
            if c.value is None:
                continue
            txt = str(c.value).strip()
            if "DOSES SUPPLEMENTAIRES" in normaliser(txt):
                return {c.coordinate: f"{txt} : {nombre}"}
    return {}


def edits_mise_en_eau(ws, nb_wc: int) -> dict[str, str]:
    """WC autonomes : renseigne « Mise en eau + 1 dose » avec le NOMBRE de WC de l'état (1 par WC).

    Ex. 3 WC autonomes -> 3 mises en eau. Dict vide si le libellé est absent ou nb_wc <= 0.
    """
    if not nb_wc or nb_wc <= 0:
        return {}
    for row in ws.iter_rows():
        for c in row:
            if c.value is None:
                continue
            txt = str(c.value).strip()
            if "MISE EN EAU" in normaliser(txt):
                return {c.coordinate: f"{txt} : {nb_wc}"}
    return {}


def onglet_douches(nb_douches: int | None) -> str:
    """R1 : onglet du modèle DOUCHES selon le nombre (≈4 -> petit, ≈6 -> grand)."""
    return "Grand Sanitaire Douche" if (nb_douches or 0) >= 5 else "Petit Sanitaire Douche"
