"""Documents attachés à un chantier + navigation / accès du rôle chauffeur."""

from fastapi.testclient import TestClient

from app import db
from app.generation import generer
from app.main import app
from app.securite import hacher

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d4944415478da63fcffff3f030005fe02fea72d34490000000049454e44ae426082"
)


def _chantier_demo() -> int:
    """Génère le dossier EIFFAGE de démo (crée client + chantier) et renvoie un chantier_id."""
    generer(None, utiliser_fixture=True)
    with db._conn() as cx:
        return cx.execute("SELECT id FROM chantiers ORDER BY id LIMIT 1").fetchone()[0]


def test_ajout_document_puis_lecture():
    cid = _chantier_demo()
    tc = TestClient(app)
    r = tc.post(f"/chantiers/{cid}/documents", files={"fichier": ("scan.png", PNG, "image/png")})
    assert r.status_code == 200
    docs = r.json()["documents"]
    assert len(docs) == 1 and docs[0]["nom_affiche"] == "scan.png"
    doc_id = docs[0]["id"]
    # Le fichier se télécharge et correspond à l'octet près.
    g = tc.get(f"/chantiers/{cid}/documents/{doc_id}")
    assert g.status_code == 200 and g.content == PNG
    # Le contenu du chantier expose bien ses documents.
    assert tc.get(f"/chantiers/{cid}").json()["documents"][0]["id"] == doc_id


def test_format_non_autorise_refuse():
    cid = _chantier_demo()
    r = TestClient(app).post(
        f"/chantiers/{cid}/documents",
        files={"fichier": ("programme.exe", b"MZ...", "application/octet-stream")},
    )
    assert r.status_code == 400


def test_document_sur_chantier_inconnu():
    r = TestClient(app).post(
        "/chantiers/999999/documents", files={"fichier": ("d.pdf", b"%PDF-1.4", "application/pdf")}
    )
    assert r.status_code == 404


def test_isolation_document_entre_chantiers():
    """Un doc n'est accessible que via SON chantier (pas de fuite d'un chantier à l'autre)."""
    cid = _chantier_demo()
    tc = TestClient(app)
    doc_id = tc.post(f"/chantiers/{cid}/documents",
                     files={"fichier": ("s.png", PNG, "image/png")}).json()["documents"][0]["id"]
    assert tc.get(f"/chantiers/{cid + 999}/documents/{doc_id}").status_code == 404


# ------------------------------------------------------------- accès chauffeur

def _comptes():
    db.creer_utilisateur("admin", "Admin", hacher("motdepasse8"), "admin")
    db.creer_utilisateur("driver", "Chauffeur", hacher("motdepasse8"), "chauffeur")


def test_chauffeur_navigue_en_lecture_et_ajoute_un_document():
    cid = _chantier_demo()
    _comptes()
    tc = TestClient(app)
    auth = ("driver", "motdepasse8")
    # Navigation autorisée : clients, fiche client, chantier.
    r = tc.get("/clients", auth=auth)
    assert r.status_code == 200
    cli_id = r.json()["clients"][0]["id"]
    assert tc.get(f"/clients/{cli_id}", auth=auth).status_code == 200
    assert tc.get(f"/chantiers/{cid}", auth=auth).status_code == 200
    # Ajout d'un document (scan terrain) autorisé.
    a = tc.post(f"/chantiers/{cid}/documents", files={"fichier": ("terrain.png", PNG, "image/png")}, auth=auth)
    assert a.status_code == 200


def test_chauffeur_ne_modifie_ni_ne_supprime():
    cid = _chantier_demo()
    _comptes()
    tc = TestClient(app)
    auth = ("driver", "motdepasse8")
    cli_id = tc.get("/clients", auth=auth).json()["clients"][0]["id"]
    # Édition d'un client : interdite (lecture seule).
    assert tc.patch(f"/clients/{cli_id}", json={"ville": "X"}, auth=auth).status_code == 403
    # Suppression d'un document : réservée à l'admin.
    doc_id = tc.post(f"/chantiers/{cid}/documents", files={"fichier": ("s.png", PNG, "image/png")},
                     auth=auth).json()["documents"][0]["id"]
    assert tc.delete(f"/chantiers/{cid}/documents/{doc_id}", auth=auth).status_code == 403
    assert tc.delete(f"/chantiers/{cid}/documents/{doc_id}", auth=("admin", "motdepasse8")).status_code == 200
    # L'historique reste hors de portée du chauffeur.
    assert tc.get("/historique", auth=auth).status_code == 403
