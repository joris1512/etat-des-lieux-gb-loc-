"""Écriture de cellules dans un .xlsx SANS openpyxl, en préservant tout le reste.

openpyxl reconstruit le classeur à l'enregistrement et **perd les images et les dessins**
(logo GB, perspectives du module). Pour pré-remplir quelques cellules tout en gardant le
modèle intact (logo, dessins, mise en forme, autres onglets), on modifie directement le XML
de la feuille ciblée dans l'archive .xlsx ; toutes les autres parties sont recopiées telles quelles.

On n'écrit que des valeurs simples (chaînes ou nombres) dans des cellules désignées par leur
référence (« E5 », « A9 »…). Les cellules existent en général déjà dans le modèle ; sinon elles
sont insérées dans la bonne ligne.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _echapper(texte: str) -> str:
    return (
        texte.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def _col_index(ref: str) -> int:
    """'E5' -> 5 (index 1-based de la colonne)."""
    lettres = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for c in lettres:
        n = n * 26 + (ord(c) - 64)
    return n


def _row_num(ref: str) -> int:
    return int(re.search(r"\d+", ref).group(0))


def _chemin_feuille(items: dict[str, bytes], feuille: str | None) -> str:
    """Chemin XML de la feuille (par nom, sinon la 1re). Lève si introuvable."""
    wb = items["xl/workbook.xml"].decode("utf-8")
    sheets = re.findall(r"<sheet\b[^>]*/>", wb)
    cible_rid = None
    if feuille is None:
        m = re.search(r'r:id="([^"]+)"', sheets[0]) if sheets else None
        cible_rid = m.group(1) if m else None
    else:
        for s in sheets:
            nom = re.search(r'name="([^"]*)"', s)
            if nom and nom.group(1) == feuille:
                rid = re.search(r'r:id="([^"]+)"', s)
                cible_rid = rid.group(1) if rid else None
                break
        if cible_rid is None:
            raise ValueError(f"Feuille « {feuille} » absente du modèle.")
    rels = items["xl/_rels/workbook.xml.rels"].decode("utf-8")
    target = None
    for rel in re.findall(r"<Relationship\b[^>]*?/?>", rels):
        if re.search(rf'\bId="{re.escape(cible_rid)}"', rel):  # ordre des attributs indifférent
            tm = re.search(r'\bTarget="([^"]+)"', rel)
            target = tm.group(1) if tm else None
            break
    if not target:
        raise ValueError("Relation de feuille introuvable dans le modèle.")
    target = target.lstrip("/")
    return target if target.startswith("xl/") else "xl/" + target


def _cellule_xml(ref: str, valeur: object, style: str) -> str:
    """Construit le <c> pour une chaîne (inlineStr) ou un nombre."""
    if isinstance(valeur, bool):
        valeur = str(valeur)
    if isinstance(valeur, (int, float)):
        return f'<c r="{ref}"{style}><v>{valeur}</v></c>'
    txt = _echapper(str(valeur))
    return f'<c r="{ref}"{style} t="inlineStr"><is><t xml:space="preserve">{txt}</t></is></c>'


def _ecrire_une(xml: str, ref: str, valeur: object) -> str:
    """Remplace la cellule `ref` (en gardant son style) ou l'insère dans sa ligne."""
    pat = re.compile(rf'<c r="{ref}"([^>]*?)(/>|>.*?</c>)', re.DOTALL)
    m = pat.search(xml)
    if m:
        s = re.search(r'\ss="\d+"', m.group(1))
        style = s.group(0) if s else ""
        return xml[: m.start()] + _cellule_xml(ref, valeur, style) + xml[m.end() :]

    # Cellule absente : on l'insère dans sa ligne (créée au besoin), en ordre de colonne.
    neuf = _cellule_xml(ref, valeur, "")
    row = _row_num(ref)
    col = _col_index(ref)
    rowpat = re.compile(rf'(<row r="{row}"[^>]*>)(.*?)(</row>)', re.DOTALL)
    rm = rowpat.search(xml)
    if rm:
        contenu = rm.group(2)
        pos = len(contenu)  # par défaut : en fin de ligne
        for cm in re.finditer(r'<c r="([A-Z]+\d+)"', contenu):
            if _col_index(cm.group(1)) > col:
                pos = cm.start()  # avant la 1re cellule de colonne supérieure
                break
        contenu2 = contenu[:pos] + neuf + contenu[pos:]
        return xml[: rm.start()] + rm.group(1) + contenu2 + rm.group(3) + xml[rm.end() :]

    # Ligne absente : on insère <row> dans <sheetData>, en ordre de ligne.
    rowxml = f'<row r="{row}">{neuf}</row>'
    sd = re.search(r"(<sheetData[^>]*>)(.*?)(</sheetData>)", xml, re.DOTALL)
    if not sd:
        raise ValueError("sheetData introuvable.")
    rows = re.findall(r'<row r="(\d+)"', sd.group(2))
    inner = sd.group(2)
    insert_at = len(inner)
    for rr in rows:
        if int(rr) > row:
            mrow = re.search(rf'<row r="{rr}"', inner)
            insert_at = mrow.start()
            break
    inner2 = inner[:insert_at] + rowxml + inner[insert_at:]
    return xml[: sd.start()] + sd.group(1) + inner2 + sd.group(3) + xml[sd.end() :]


def ecrire_cellules(
    modele: Path, sortie: Path, feuille: str | None, valeurs: dict[str, object]
) -> None:
    """Écrit `valeurs` (réf -> valeur) sur `feuille` de `modele`, vers `sortie`, tout préservé."""
    with zipfile.ZipFile(modele) as zin:
        items = {n: zin.read(n) for n in zin.namelist()}
    cible = _chemin_feuille(items, feuille)
    xml = items[cible].decode("utf-8")
    for ref, valeur in valeurs.items():
        if valeur is None or valeur == "":
            continue
        xml = _ecrire_une(xml, ref, valeur)
    items[cible] = xml.encode("utf-8")
    sortie.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(sortie, "w", zipfile.ZIP_DEFLATED) as zout:
        for nom, data in items.items():
            zout.writestr(nom, data)
