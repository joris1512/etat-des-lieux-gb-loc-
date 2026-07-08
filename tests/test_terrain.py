"""Mode chauffeur : constat écrit dans l'Excel, photos, signature, PDF, gardes des endpoints."""

import zipfile

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app import terrain
from app.assemblage import construire_plan
from app.extraction import charger_fixture
from app.generation import generer
from app.main import app

PNG_MINIMAL = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG_MINIMAL = b"\xff\xd8\xff\xe0" + b"\x00" * 64


def _document_bungalow():
    rapport, job_dir = generer(None, utiliser_fixture=True)
    par_nom = {e.nom_fichier: e for e in construire_plan(charger_fixture()).etats}
    nom = next(n for n in rapport.fichiers if par_nom[n].type_etat == "individuel")
    return job_dir, nom


def test_lignes_detectees_sur_document_reel():
    job_dir, nom = _document_bungalow()
    lignes = terrain.lignes_depuis_modele(job_dir / nom, None)
    libelles = [x["libelle"] for x in lignes]
    assert len(lignes) >= 8
    assert any("Sol" in x for x in libelles)
    assert any("Radiateur" in x for x in libelles)


def test_constat_ecrit_dans_excel_et_recharge():
    job_dir, nom = _document_bungalow()
    doc = job_dir / nom
    dossier = terrain.dossier_constat(job_dir, nom)
    lignes = terrain.lignes_depuis_modele(doc, None)
    cible = next(x for x in lignes if "Sol" in x["libelle"])
    cible["debut"] = "Bon état"
    cible["fin"] = "Rayure 20 cm"
    terrain.enregistrer_constat(doc, None, lignes, dossier)

    ws = load_workbook(doc).active
    assert ws[f"C{cible['ligne']}"].value == "Bon état"
    assert ws[f"F{cible['ligne']}"].value == "Rayure 20 cm"
    with zipfile.ZipFile(doc) as z:  # logo + perspectives toujours là
        assert any("drawing" in n for n in z.namelist())
    recharge = terrain.charger_constat(doc, None, dossier)
    assert any(x.get("debut") == "Bon état" for x in recharge["lignes"])


def test_photos_validees_et_numerotees(tmp_path):
    d = tmp_path / "constat"
    d.mkdir()
    assert terrain.ajouter_photo(d, JPEG_MINIMAL) == "photo-01.jpg"
    assert terrain.ajouter_photo(d, PNG_MINIMAL) == "photo-02.png"
    with pytest.raises(ValueError):
        terrain.ajouter_photo(d, b"<script>pas une image</script>")


def test_signature_et_pdf(tmp_path):
    d = tmp_path / "constat"
    d.mkdir()
    with pytest.raises(ValueError):
        terrain.enregistrer_signature(d, b"pas un png", "X")
    terrain.enregistrer_signature(d, PNG_MINIMAL, "M. Client")
    assert (d / "signature.png").exists()
    pdf = terrain.generer_pdf(d, titre="Bungalow 1", sous_titre="ACME · Chantier X", societe="GB")
    assert pdf.exists() and pdf.read_bytes()[:4] == b"%PDF"


def test_endpoints_constat(monkeypatch):
    import app.main as main_mod
    from app import generation

    monkeypatch.setattr(main_mod, "SORTIES_DIR", generation.SORTIES_DIR)
    job_dir, nom = _document_bungalow()
    tc = TestClient(app)
    base = f"/terrain/{job_dir.name}/{nom}"

    d = tc.get(base)
    assert d.status_code == 200 and len(d.json()["lignes"]) >= 8

    lignes = d.json()["lignes"]
    lignes[0]["debut"] = "RAS"
    r = tc.post(base, json={"lignes": lignes})
    assert r.status_code == 200
    assert any(x.get("debut") == "RAS" for x in r.json()["lignes"])

    # Photo refusée si fausse image ; acceptée sinon, puis servie ; traversal refusé.
    assert tc.post(base + "/photo", files={"fichier": ("x.jpg", b"<html>", "image/jpeg")}).status_code == 400
    r = tc.post(base + "/photo", files={"fichier": ("x.jpg", JPEG_MINIMAL, "image/jpeg")})
    assert r.status_code == 200 and r.json()["photos"] == ["photo-01.jpg"]
    assert tc.get(f"/terrain-fichier/{job_dir.name}/{nom}/photo-01.jpg").status_code == 200
    assert tc.get(f"/terrain-fichier/{job_dir.name}/{nom}/..%5Cgb.db").status_code in (400, 404)

    # Signature + PDF.
    import base64

    image = "data:image/png;base64," + base64.b64encode(PNG_MINIMAL).decode()
    r = tc.post(base + "/signature", json={"image": image, "signataire": "M. Client"})
    assert r.status_code == 200 and r.json()["signature"] is True
    r = tc.post(base + "/pdf")
    assert r.status_code == 200 and r.json()["pdf"] == "constat.pdf"
    assert tc.get(f"/terrain-fichier/{job_dir.name}/{nom}/constat.pdf").status_code == 200

    # Partage : réservé au poste local (TestClient n'est pas local -> 403).
    assert tc.post(base + "/partager").status_code == 403
