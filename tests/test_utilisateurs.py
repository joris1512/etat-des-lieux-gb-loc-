"""Comptes utilisateurs nominatifs : auth en base, rôles, garde admin, dernier admin protégé."""

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app
from app.securite import hacher


def _creer(identifiant="j.dupont", role="admin", mdp="motdepasse8", nom="Jean Dupont"):
    return db.creer_utilisateur(identifiant, nom, hacher(mdp), role)


def test_sans_compte_acces_libre():
    r = TestClient(app).get("/etat")
    assert r.status_code == 200
    assert r.json()["auth"] is False
    assert r.json()["utilisateur"] == "poste-local"


def test_un_compte_active_la_connexion():
    _creer()
    tc = TestClient(app)
    assert tc.get("/modeles").status_code == 401  # sans identifiants
    r = tc.get("/etat", auth=("j.dupont", "motdepasse8"))
    assert r.status_code == 200
    assert r.json()["utilisateur"] == "j.dupont"
    assert r.json()["role"] == "admin"


def test_mauvais_mot_de_passe_refuse():
    _creer()
    assert TestClient(app).get("/modeles", auth=("j.dupont", "mauvais")).status_code == 401


def test_compte_desactive_refuse():
    uid = _creer()
    _creer("second.admin")  # pour pouvoir désactiver le premier
    db.modifier_utilisateur(uid, actif=False)
    assert TestClient(app).get("/modeles", auth=("j.dupont", "motdepasse8")).status_code == 401


def test_non_admin_ne_gere_pas_les_comptes():
    _creer()  # admin
    _creer("p.martin", role="utilisateur", nom="Paul Martin")
    tc = TestClient(app)
    assert tc.get("/utilisateurs", auth=("p.martin", "motdepasse8")).status_code == 403
    # ... mais il utilise l'application normalement.
    assert tc.get("/modeles", auth=("p.martin", "motdepasse8")).status_code == 200
    # L'admin, lui, gère les comptes.
    r = tc.get("/utilisateurs", auth=("j.dupont", "motdepasse8"))
    assert r.status_code == 200 and len(r.json()["utilisateurs"]) == 2


def test_dernier_admin_indestructible():
    uid = _creer()
    with pytest.raises(ValueError):
        db.modifier_utilisateur(uid, actif=False)


def test_creation_endpoint_valide_le_mot_de_passe():
    _creer()
    r = TestClient(app).post(
        "/utilisateurs",
        json={"identifiant": "x", "mot_de_passe": "court"},
        auth=("j.dupont", "motdepasse8"),
    )
    assert r.status_code == 400


def test_identifiant_duplique_refuse():
    _creer()
    with pytest.raises(ValueError):
        _creer("J.DUPONT")  # insensible à la casse
