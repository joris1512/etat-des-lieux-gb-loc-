"""Mode chauffeur (terrain) : constat début/fin, photos, signature électronique, PDF.

Le document Excel généré reste la référence : les valeurs saisies sont écrites dans ses
colonnes « Début de loc » (C) / « Fin de loc » (F) via patch_xlsx (logo et perspectives
préservés). Un dossier « constat - <document> » accolé au document reçoit les photos, la
signature et le PDF de constat ; l'état de saisie vit dans constat.json (rechargeable).
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook

from app import patch_xlsx

PHOTOS_MAX = 20
_POINTILLES = {".", "…", " ", " "}


def _est_pointille(v) -> bool:
    """True si la cellule ne contient qu'un gabarit de pointillés (ligne à remplir)."""
    return isinstance(v, str) and len(v.strip()) > 3 and set(v.strip()) <= _POINTILLES


def dossier_constat(job_dir: Path, nom_fichier: str) -> Path:
    """Dossier des pièces du constat (photos, signature, PDF), accolé au document."""
    d = job_dir / f"constat - {Path(nom_fichier).stem}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _chemin_json(dossier: Path) -> Path:
    return dossier / "constat.json"


def lignes_depuis_modele(chemin: Path, feuille: str | None) -> list[dict]:
    """Repère les lignes d'inspection du document : libellé (col. A) + cases C/F en pointillés."""
    wb = load_workbook(chemin, data_only=True)
    ws = wb[feuille] if feuille and feuille in wb.sheetnames else wb[wb.sheetnames[0]]
    lignes: list[dict] = []
    dernier_libelle = ""
    suite = 0
    for r in range(1, ws.max_row + 1):
        c, f = ws.cell(row=r, column=3).value, ws.cell(row=r, column=6).value
        if not (_est_pointille(c) or _est_pointille(f)):
            continue
        a = ws.cell(row=r, column=1).value
        libelle = " ".join(str(a).split()) if isinstance(a, str) and str(a).strip() else ""
        if libelle:
            dernier_libelle, suite = libelle, 0
        else:
            suite += 1
            libelle = f"{dernier_libelle} (suite {suite})" if dernier_libelle else f"Ligne {r}"
        lignes.append({"ligne": r, "libelle": libelle, "debut": "", "fin": ""})
    wb.close()
    return lignes


def charger_constat(document: Path, feuille: str | None, dossier: Path) -> dict:
    """État complet du constat : lignes (sauvegardées ou détectées), photos, signature, PDF."""
    js = _chemin_json(dossier)
    if js.exists():
        data = json.loads(js.read_text(encoding="utf-8"))
    else:
        data = {"feuille": feuille, "lignes": lignes_depuis_modele(document, feuille)}
    data["photos"] = sorted(p.name for p in dossier.glob("photo-*.*"))
    data["signature"] = (dossier / "signature.png").exists()
    data["signataire"] = data.get("signataire", "")
    data["pdf"] = "constat.pdf" if (dossier / "constat.pdf").exists() else None
    return data


def enregistrer_constat(document: Path, feuille: str | None, lignes: list[dict], dossier: Path) -> None:
    """Écrit début/fin dans le document Excel (C{r}/F{r}) et persiste l'état de saisie."""
    valeurs: dict[str, object] = {}
    for ligne in lignes:
        r = int(ligne.get("ligne", 0))
        if r <= 0:
            continue
        debut = str(ligne.get("debut") or "").strip()
        fin = str(ligne.get("fin") or "").strip()
        if debut:
            valeurs[f"C{r}"] = debut
        if fin:
            valeurs[f"F{r}"] = fin
    if valeurs:
        patch_xlsx.ecrire_cellules(document, document, feuille, valeurs)
    js = _chemin_json(dossier)
    ancien = json.loads(js.read_text(encoding="utf-8")) if js.exists() else {}
    ancien.update({
        "feuille": feuille,
        "lignes": lignes,
        "maj": datetime.now().isoformat(timespec="seconds"),
    })
    js.write_text(json.dumps(ancien, ensure_ascii=False, indent=1), encoding="utf-8")


def ajouter_photo(dossier: Path, contenu: bytes) -> str:
    """Enregistre une photo (JPEG/PNG vérifiés par signature de fichier)."""
    if contenu.startswith(b"\xff\xd8\xff"):
        ext = "jpg"
    elif contenu.startswith(b"\x89PNG\r\n\x1a\n"):
        ext = "png"
    else:
        raise ValueError("Format accepté : JPEG ou PNG.")
    existantes = list(dossier.glob("photo-*.*"))
    if len(existantes) >= PHOTOS_MAX:
        raise ValueError(f"Maximum {PHOTOS_MAX} photos par constat.")
    numeros = [int(m.group(1)) for p in existantes if (m := re.match(r"photo-(\d+)", p.stem))]
    nom = f"photo-{(max(numeros) + 1) if numeros else 1:02d}.{ext}"
    (dossier / nom).write_bytes(contenu)
    return nom


def _ancre_signature(document: Path, feuille: str | None) -> str | None:
    """Cellule sous la zone « Date, Nom et Signature » côté client (colonne E des modèles)."""
    wb = load_workbook(document, data_only=True)
    ws = wb[feuille] if feuille and feuille in wb.sheetnames else wb[wb.sheetnames[0]]
    ancre = None
    for row in ws.iter_rows(max_col=8):
        for c in row:
            if isinstance(c.value, str) and "Signature" in c.value and "mention" not in c.value:
                ancre = f"{c.column_letter}{c.row + 1}"  # juste sous le libellé
    wb.close()
    return ancre


def enregistrer_signature(
    dossier: Path, png: bytes, signataire: str, document: Path | None = None
) -> None:
    if not png.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Signature invalide.")
    (dossier / "signature.png").write_bytes(png)
    # Insère aussi la signature DANS le document Excel (zone « Date, Nom et Signature »).
    if document is not None and document.exists():
        try:
            ancre = _ancre_signature(document, None)
            if ancre:
                patch_xlsx.inserer_image(document, None, ancre, png)
        except Exception:  # noqa: BLE001 — l'insertion Excel ne doit pas bloquer la signature
            pass
    js = _chemin_json(dossier)
    data = json.loads(js.read_text(encoding="utf-8")) if js.exists() else {}
    data["signataire"] = (signataire or "").strip()
    data["signe_le"] = datetime.now().strftime("%d/%m/%Y à %H:%M")
    js.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def generer_pdf(dossier: Path, titre: str, sous_titre: str, societe: str = "") -> Path:
    """PDF de constat : en-tête, relevés début/fin, photos, signature datée."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas as rl_canvas

    js = _chemin_json(dossier)
    data = json.loads(js.read_text(encoding="utf-8")) if js.exists() else {"lignes": []}
    cible = dossier / "constat.pdf"
    c = rl_canvas.Canvas(str(cible), pagesize=A4)
    largeur, hauteur = A4
    marge = 18 * mm

    def entete_page() -> float:
        c.setFont("Helvetica-Bold", 15)
        c.drawString(marge, hauteur - marge, f"Constat d'état des lieux — {societe or 'GB Location'}")
        c.setFont("Helvetica", 10)
        c.drawString(marge, hauteur - marge - 14, titre)
        c.drawString(marge, hauteur - marge - 26, sous_titre)
        c.setFillColor(colors.grey)
        c.drawRightString(largeur - marge, hauteur - marge, datetime.now().strftime("%d/%m/%Y %H:%M"))
        c.setFillColor(colors.black)
        c.line(marge, hauteur - marge - 32, largeur - marge, hauteur - marge - 32)
        return hauteur - marge - 46

    y = entete_page()
    # --- Relevés ---
    c.setFont("Helvetica-Bold", 9)
    c.drawString(marge, y, "Élément")
    c.drawString(marge + 78 * mm, y, "Début de location")
    c.drawString(marge + 128 * mm, y, "Fin de location")
    y -= 12
    c.setFont("Helvetica", 9)
    for ligne in data.get("lignes", []):
        if y < 30 * mm:
            c.showPage()
            y = entete_page()
            c.setFont("Helvetica", 9)
        c.drawString(marge, y, str(ligne.get("libelle", ""))[:52])
        c.drawString(marge + 78 * mm, y, str(ligne.get("debut", ""))[:34])
        c.drawString(marge + 128 * mm, y, str(ligne.get("fin", ""))[:34])
        y -= 11

    # --- Photos ---
    photos = sorted(dossier.glob("photo-*.*"))
    if photos:
        c.showPage()
        y = entete_page()
        c.setFont("Helvetica-Bold", 11)
        c.drawString(marge, y, f"Photos ({len(photos)})")
        y -= 8
        larg_img = (largeur - 2 * marge - 8 * mm) / 2
        haut_img = 62 * mm
        x = marge
        col = 0
        y -= haut_img
        for p in photos:
            try:
                img = ImageReader(str(p))
                c.drawImage(img, x, y, width=larg_img, height=haut_img,
                            preserveAspectRatio=True, anchor="sw")
                c.setFont("Helvetica", 7)
                c.setFillColor(colors.grey)
                c.drawString(x, y - 8, p.name)
                c.setFillColor(colors.black)
            except Exception:  # noqa: BLE001 — une photo illisible ne bloque pas le constat
                continue
            col += 1
            if col % 2 == 0:
                x = marge
                y -= haut_img + 14
                if y < 30 * mm:
                    c.showPage()
                    y = entete_page() - haut_img
            else:
                x = marge + larg_img + 8 * mm

    # --- Signature ---
    sig = dossier / "signature.png"
    if sig.exists():
        if y < 70 * mm:
            c.showPage()
            y = entete_page()
        c.setFont("Helvetica-Bold", 10)
        c.drawString(marge, 58 * mm, "Signature du client — « bon pour accord »")
        c.setFont("Helvetica", 9)
        qui = data.get("signataire") or ""
        quand = data.get("signe_le") or ""
        c.drawString(marge, 52 * mm, f"{qui}   ·   signé le {quand}")
        try:
            c.drawImage(ImageReader(str(sig)), marge, 20 * mm, width=70 * mm, height=28 * mm,
                        preserveAspectRatio=True, anchor="sw", mask="auto")
        except Exception:  # noqa: BLE001
            pass
    c.save()
    return cible
