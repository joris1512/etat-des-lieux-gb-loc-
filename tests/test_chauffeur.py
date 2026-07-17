"""Espace chauffeurs : rôle restreint, signature insérée dans l'Excel, accès mobile."""

import shutil
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from app import db, patch_xlsx, terrain
from app.main import app
from app.securite import hacher

MODELE = Path(__file__).parent.parent / "templates" / "bungalow_vide.xlsx"

# Signature de test : PNG 1x1 valide.
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d4944415478da63fcffff3f030005fe02fea72d34490000000049454e44ae426082"
)


def _comptes():
    db.creer_utilisateur("admin", "Admin", hacher("motdepasse8"), "admin")
    db.creer_utilisateur("chauffeur1", "Karim", hacher("motdepasse8"), "chauffeur")


# ---------------------------------------------------------------- rôle chauffeur

def test_role_chauffeur_accepte():
    uid = db.creer_utilisateur("c1", "C", hacher("motdepasse8"), "chauffeur")
    u = [x for x in db.lister_utilisateurs() if x["id"] == uid][0]
    assert u["role"] == "chauffeur"


def test_chauffeur_acces_constats_mais_pas_au_reste():
    _comptes()
    tc = TestClient(app)
    auth = ("chauffeur1", "motdepasse8")
    # Autorisé : son espace.
    assert tc.get("/etat", auth=auth).status_code == 200
    assert tc.get("/constats", auth=auth).status_code == 200
    assert tc.get("/", auth=auth).status_code == 200
    # Interdit : tout le reste de l'application.
    assert tc.get("/clients", auth=auth).status_code == 403
    assert tc.get("/historique", auth=auth).status_code == 403
    assert tc.get("/stats", auth=auth).status_code == 403
    assert tc.get("/modeles", auth=auth).status_code == 403
    assert tc.get("/utilisateurs", auth=auth).status_code == 403
    # L'admin, lui, passe partout.
    assert tc.get("/clients", auth=("admin", "motdepasse8")).status_code == 200


def test_etat_expose_le_role():
    _comptes()
    r = TestClient(app).get("/etat", auth=("chauffeur1", "motdepasse8"))
    assert r.json()["role"] == "chauffeur"


# ------------------------------------------------------- signature dans l'Excel

def test_inserer_image_ajoute_la_signature(tmp_path):
    doc = tmp_path / "etat.xlsx"
    shutil.copy(MODELE, doc)
    with zipfile.ZipFile(doc) as z:
        avant = set(z.namelist())
    assert patch_xlsx.inserer_image(doc, None, "E48", PNG) is True
    with zipfile.ZipFile(doc) as z:
        apres = set(z.namelist())
        assert "xl/media/signature_gb.png" in apres
        assert avant <= apres  # rien de perdu (logo, perspectives, feuilles)
        dessin = next(n for n in apres if n.startswith("xl/drawings/") and n.endswith(".xml"))
        xml = z.read(dessin).decode("utf-8")
        assert xml.count("oneCellAnchor") >= 1 and "Signature client" in xml


def test_re_signature_ne_duplique_pas(tmp_path):
    doc = tmp_path / "etat.xlsx"
    shutil.copy(MODELE, doc)
    assert patch_xlsx.inserer_image(doc, None, "E48", PNG) is True
    assert patch_xlsx.inserer_image(doc, None, "E48", PNG) is True
    with zipfile.ZipFile(doc) as z:
        dessin = next(n for n in z.namelist() if n.startswith("xl/drawings/") and n.endswith(".xml"))
        assert z.read(dessin).decode("utf-8").count("Signature client") == 1


def test_ancre_signature_detectee():
    assert terrain._ancre_signature(MODELE, None) == "E48"


def test_enregistrer_signature_embarque_dans_le_document(tmp_path):
    doc = tmp_path / "etat.xlsx"
    shutil.copy(MODELE, doc)
    dossier = tmp_path / "constat"
    dossier.mkdir()
    terrain.enregistrer_signature(dossier, PNG, "M. Client", document=doc)
    assert (dossier / "signature.png").exists()
    with zipfile.ZipFile(doc) as z:
        assert "xl/media/signature_gb.png" in z.namelist()


# ------------------------------------------------------------------ accès mobile

def test_mobile_reserve_aux_admins():
    _comptes()
    tc = TestClient(app)
    assert tc.get("/mobile-infos", auth=("chauffeur1", "motdepasse8")).status_code == 403
    r = tc.get("/mobile-infos", auth=("admin", "motdepasse8"))
    assert r.status_code == 200 and r.json()["port"] == 8742


def test_mobile_acces_ecrit_le_parametre():
    _comptes()
    tc = TestClient(app)
    r = tc.post("/mobile-acces", json={"actif": True}, auth=("admin", "motdepasse8"))
    assert r.status_code == 200 and r.json()["actif"] is True
    assert db.lire_parametre("acces_mobile", "0") == "1"
    tc.post("/mobile-acces", json={"actif": False}, auth=("admin", "motdepasse8"))
    assert db.lire_parametre("acces_mobile", "0") == "0"


def test_manifest_pwa():
    r = TestClient(app).get("/manifest.json")
    assert r.status_code == 200
    assert r.json()["display"] == "standalone"
