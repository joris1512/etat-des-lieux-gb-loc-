"""Marque blanche : nom de société + logo (garde admin, validation d'image)."""

from fastapi.testclient import TestClient

import app.main as main_mod
from app import db
from app.main import app
from app.securite import hacher

PNG_MINIMAL = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def test_parametres_par_defaut():
    r = TestClient(app).get("/parametres")
    assert r.status_code == 200
    assert r.json()["societe"] == ""
    assert r.json()["logo"].endswith("logo.png")


def test_nom_societe_enregistre_et_affiche():
    tc = TestClient(app)
    r = tc.post("/parametres", json={"societe": "LOCAMODULE SAS"})
    assert r.status_code == 200 and r.json()["societe"] == "LOCAMODULE SAS"
    assert tc.get("/parametres").json()["societe"] == "LOCAMODULE SAS"
    assert db.lire_parametre("societe") == "LOCAMODULE SAS"


def test_logo_valide_par_signature(tmp_path, monkeypatch):
    monkeypatch.setattr(main_mod, "STATIC_DIR", tmp_path)
    tc = TestClient(app)
    # Un faux « logo » HTML est refusé, un PNG accepté, le défaut restaurable.
    r = tc.post("/parametres/logo", files={"fichier": ("x.png", b"<html>hack</html>", "image/png")})
    assert r.status_code == 400
    r = tc.post("/parametres/logo", files={"fichier": ("logo.png", PNG_MINIMAL, "image/png")})
    assert r.status_code == 200 and r.json()["logo"].endswith("logo_client.png")
    assert (tmp_path / "logo_client.png").exists()
    assert tc.delete("/parametres/logo").status_code == 200
    assert not (tmp_path / "logo_client.png").exists()


def test_parametres_reserves_aux_admins():
    db.creer_utilisateur("p.martin", "Paul Martin", hacher("motdepasse8"), "utilisateur")
    db.creer_utilisateur("chef", "Chef", hacher("motdepasse8"), "admin")
    tc = TestClient(app)
    # Lecture : ouverte (l'UI affiche la marque à tous) ; écriture : admin uniquement.
    assert tc.get("/parametres", auth=("p.martin", "motdepasse8")).status_code == 200
    r = tc.post("/parametres", json={"societe": "X"}, auth=("p.martin", "motdepasse8"))
    assert r.status_code == 403
    r = tc.post("/parametres", json={"societe": "X"}, auth=("chef", "motdepasse8"))
    assert r.status_code == 200
