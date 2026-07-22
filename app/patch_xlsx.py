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


def _style_index_actuel(xml: str, ref: str) -> int:
    """Index de style (`s="N"`) de la cellule `ref` dans le modèle (0 si absent)."""
    m = re.search(rf'<c r="{ref}"([^>]*?)(/>|>.*?</c>)', xml, re.DOTALL)
    if m:
        s = re.search(r'\ss="(\d+)"', m.group(1))
        if s:
            return int(s.group(1))
    return 0


def _ecrire_une(xml: str, ref: str, valeur: object, style_force: str | None = None) -> str:
    """Remplace la cellule `ref` (en gardant son style, ou `style_force`) ou l'insère dans sa ligne."""
    pat = re.compile(rf'<c r="{ref}"([^>]*?)(/>|>.*?</c>)', re.DOTALL)
    m = pat.search(xml)
    if m:
        if style_force is not None:
            style = style_force
        else:
            s = re.search(r'\ss="\d+"', m.group(1))
            style = s.group(0) if s else ""
        return xml[: m.start()] + _cellule_xml(ref, valeur, style) + xml[m.end() :]

    # Cellule absente : on l'insère dans sa ligne (créée au besoin), en ordre de colonne.
    neuf = _cellule_xml(ref, valeur, style_force or "")
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


_EMU_PAR_POUCE = 914400


def inserer_image(
    xlsx: Path, feuille: str | None, cellule: str, png: bytes,
    largeur_po: float = 2.2, hauteur_po: float = 0.85,
) -> bool:
    """Insère un PNG (ex. signature) ancré sur `cellule`, en préservant tout le classeur.

    S'appuie sur le drawing DÉJÀ présent sur la feuille (tous nos modèles en ont un : logo,
    perspectives). Re-signature : remplace l'image existante au lieu d'en empiler une nouvelle.
    Renvoie False si la feuille n'a pas de drawing (image non insérée, sans erreur).
    """
    with zipfile.ZipFile(xlsx) as zin:
        items = {n: zin.read(n) for n in zin.namelist()}

    chemin_feuille = _chemin_feuille(items, feuille)
    xml_feuille = items[chemin_feuille].decode("utf-8")
    m = re.search(r'<drawing r:id="([^"]+)"', xml_feuille)
    if not m:
        return False
    rid_drawing = m.group(1)

    nom_court = chemin_feuille.rsplit("/", 1)[1]
    rels_feuille = items.get(f"xl/worksheets/_rels/{nom_court}.rels", b"").decode("utf-8")
    cible = None
    for rel in re.findall(r"<Relationship\b[^>]*?/?>", rels_feuille):
        if re.search(rf'\bId="{re.escape(rid_drawing)}"', rel):
            cible = re.search(r'\bTarget="([^"]+)"', rel).group(1)
            break
    if not cible:
        return False
    chemin_drawing = "xl/" + cible.replace("../", "")
    nom_drawing = chemin_drawing.rsplit("/", 1)[1]
    chemin_rels_drawing = f"xl/drawings/_rels/{nom_drawing}.rels"

    # 1) L'image dans le paquet (remplacée si déjà présente = re-signature).
    chemin_media = "xl/media/signature_gb.png"
    deja = chemin_media in items
    items[chemin_media] = png

    if not deja:
        # 2) Content-type png (Default) si absent.
        ct = items["[Content_Types].xml"].decode("utf-8")
        if 'Extension="png"' not in ct:
            ct = ct.replace(
                "</Types>",
                '<Default Extension="png" ContentType="image/png"/></Types>',
            )
            items["[Content_Types].xml"] = ct.encode("utf-8")

        # 3) Relationship du drawing vers l'image.
        if chemin_rels_drawing in items:
            rels = items[chemin_rels_drawing].decode("utf-8")
        else:
            rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"></Relationships>')
        ids = re.findall(r'Id="rId(\d+)"', rels)
        rid_img = f"rId{max((int(i) for i in ids), default=0) + 1}"
        rels = rels.replace(
            "</Relationships>",
            f'<Relationship Id="{rid_img}" Type="{_REL_NS}/image" Target="../media/signature_gb.png"/></Relationships>',
        )
        items[chemin_rels_drawing] = rels.encode("utf-8")

        # 4) L'ancre dans le drawing (oneCellAnchor sur la cellule).
        col, row = _col_index(cellule) - 1, _row_num(cellule) - 1
        cx, cy = int(largeur_po * _EMU_PAR_POUCE), int(hauteur_po * _EMU_PAR_POUCE)
        dessin = items[chemin_drawing].decode("utf-8")
        idm = re.findall(r'id="(\d+)"', dessin)
        id_forme = max((int(i) for i in idm), default=100) + 1
        ancre = (
            f'<xdr:oneCellAnchor><xdr:from><xdr:col>{col}</xdr:col><xdr:colOff>0</xdr:colOff>'
            f'<xdr:row>{row}</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:from>'
            f'<xdr:ext cx="{cx}" cy="{cy}"/>'
            f'<xdr:pic><xdr:nvPicPr><xdr:cNvPr id="{id_forme}" name="Signature client"/>'
            f'<xdr:cNvPicPr/></xdr:nvPicPr><xdr:blipFill>'
            f'<a:blip xmlns:r="{_REL_NS}" r:embed="{rid_img}"/><a:stretch><a:fillRect/></a:stretch>'
            f'</xdr:blipFill><xdr:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></xdr:spPr></xdr:pic>'
            f'<xdr:clientData/></xdr:oneCellAnchor>'
        )
        dessin = dessin.replace("</xdr:wsDr>", ancre + "</xdr:wsDr>")
        items[chemin_drawing] = dessin.encode("utf-8")

    with zipfile.ZipFile(xlsx, "w", zipfile.ZIP_DEFLATED) as zout:
        for nom, data in items.items():
            zout.writestr(nom, data)
    return True


def _style_wrap(styles_xml: str, base_index: int, cache: dict[int, int]) -> tuple[str, int]:
    """Crée (ou réutilise) une variante du style `base_index` avec « renvoi à la ligne » activé.

    Sans wrapText, les `\\n` d'une cellule s'affichent à la suite au lieu d'aller à la ligne :
    on dérive un style identique + `<alignment wrapText="1" vertical="top"/>`. Renvoie le XML des
    styles (éventuellement enrichi) et l'index du style à utiliser."""
    if base_index in cache:
        return styles_xml, cache[base_index]

    m = re.search(r'(<cellXfs count=")(\d+)("[^>]*>)(.*?)(</cellXfs>)', styles_xml, re.DOTALL)
    if not m:
        return styles_xml, base_index  # classeur sans cellXfs (rare) : on ne casse rien
    entrees = re.findall(r'<xf\b[^>]*?(?:/>|>.*?</xf>)', m.group(4), re.DOTALL)
    base = entrees[base_index] if 0 <= base_index < len(entrees) else (entrees[0] if entrees else "<xf/>")

    if "<alignment" in base:
        if "wrapText" in base:
            neuf = base  # déjà en renvoi à la ligne : rien à faire, mais on isole un index dédié
        else:
            neuf = re.sub(r'<alignment\b', '<alignment wrapText="1" vertical="top" ', base, count=1)
    elif base.endswith("/>"):
        neuf = base[:-2] + ' applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf>'
    else:  # <xf ...>...</xf> sans alignment : l'alignment doit être le 1er enfant (ordre CT_Xf)
        ouvrante = re.match(r"<xf\b[^>]*>", base).group(0)
        if "applyAlignment" not in ouvrante:
            ouvrante = ouvrante[:-1] + ' applyAlignment="1">'
        neuf = ouvrante + '<alignment wrapText="1" vertical="top"/>' + base[re.match(r"<xf\b[^>]*>", base).end():]

    nouvel_index = len(entrees)
    bloc = m.group(1) + str(nouvel_index + 1) + m.group(3) + m.group(4) + neuf + m.group(5)
    styles_xml = styles_xml[: m.start()] + bloc + styles_xml[m.end() :]
    cache[base_index] = nouvel_index
    return styles_xml, nouvel_index


def _hauteur_ligne(xml: str, row: int, nb_lignes: int) -> str:
    """Fixe une hauteur de ligne suffisante pour afficher `nb_lignes` (cases fusionnées incluses)."""
    hauteur = round(nb_lignes * 15.0, 1)
    m = re.search(rf'<row r="{row}"([^>]*?)>', xml)
    if not m:
        return xml
    attrs = re.sub(r'\s(ht|customHeight)="[^"]*"', "", m.group(1))
    return f'{xml[: m.start()]}<row r="{row}"{attrs} ht="{hauteur}" customHeight="1">{xml[m.end():]}'


def ecrire_cellules(
    modele: Path, sortie: Path, feuille: str | None, valeurs: dict[str, object]
) -> None:
    """Écrit `valeurs` (réf -> valeur) sur `feuille` de `modele`, vers `sortie`, tout préservé.

    Les valeurs multi-lignes (mobilier abondant) reçoivent le « renvoi à la ligne » et une hauteur
    de ligne adaptée pour être lisibles, au lieu de s'étaler à la suite."""
    with zipfile.ZipFile(modele) as zin:
        items = {n: zin.read(n) for n in zin.namelist()}
    cible = _chemin_feuille(items, feuille)
    xml = items[cible].decode("utf-8")
    styles_xml = items.get("xl/styles.xml", b"").decode("utf-8")
    cache_wrap: dict[int, int] = {}
    hauteurs: dict[int, int] = {}

    for ref, valeur in valeurs.items():
        if valeur is None or valeur == "":
            continue
        if isinstance(valeur, str) and "\n" in valeur and styles_xml:
            base = _style_index_actuel(xml, ref)
            styles_xml, idx = _style_wrap(styles_xml, base, cache_wrap)
            xml = _ecrire_une(xml, ref, valeur, style_force=f' s="{idx}"')
            r = _row_num(ref)
            hauteurs[r] = max(hauteurs.get(r, 0), valeur.count("\n") + 1)
        else:
            xml = _ecrire_une(xml, ref, valeur)

    for row, nb in hauteurs.items():
        xml = _hauteur_ligne(xml, row, nb)

    items[cible] = xml.encode("utf-8")
    if styles_xml:
        items["xl/styles.xml"] = styles_xml.encode("utf-8")
    sortie.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(sortie, "w", zipfile.ZIP_DEFLATED) as zout:
        for nom, data in items.items():
            zout.writestr(nom, data)
