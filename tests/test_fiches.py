"""V2 connaissance client : fiche éditable (notes, coordonnées, contacts) + stats enrichies."""

import pytest
from fastapi.testclient import TestClient

from app import db
from app.generation import generer
from app.main import app


def _client_demo() -> int:
    db.importer_client(raison_sociale="ACME SARL", numero_client="123")
    return next(c["id"] for c in db.lister_clients() if c["raison_sociale"] == "ACME SARL")


def test_modifier_fiche_et_notes():
    cid = _client_demo()
    assert db.modifier_client(cid, {"adresse": "1 rue du Port", "ville": "Bayonne",
                                    "notes": "Client fidèle — livraisons le matin uniquement."})
    c = db.lire_client(cid)
    assert c["adresse"] == "1 rue du Port"
    assert "livraisons le matin" in c["notes"]


def test_raison_sociale_vide_refusee():
    cid = _client_demo()
    with pytest.raises(ValueError):
        db.modifier_client(cid, {"raison_sociale": "  "})


def test_modifier_client_inconnu():
    assert db.modifier_client(999999, {"ville": "X"}) is False


def test_interlocuteurs_ajout_dedoublonne_et_retrait():
    cid = _client_demo()
    db.ajouter_interlocuteur(cid, "M. DUPONT")
    db.ajouter_interlocuteur(cid, "m. dupont")  # doublon insensible à la casse
    assert len(db.lire_client(cid)["interlocuteurs"]) == 1
    db.supprimer_interlocuteur(cid, "M. DUPONT")
    assert db.lire_client(cid)["interlocuteurs"] == []


def test_endpoints_fiche_client():
    cid = _client_demo()
    tc = TestClient(app)
    r = tc.patch(f"/clients/{cid}", json={"notes": "via endpoint", "code_postal": "64100"})
    assert r.status_code == 200 and r.json()["notes"] == "via endpoint"
    assert tc.patch("/clients/999999", json={"ville": "X"}).status_code == 404

    r = tc.post(f"/clients/{cid}/interlocuteurs", json={"nom": "Mme MARTIN"})
    assert r.status_code == 200
    assert any(i["nom"] == "Mme MARTIN" for i in r.json()["interlocuteurs"])
    r = tc.delete(f"/clients/{cid}/interlocuteurs", params={"nom": "Mme MARTIN"})
    assert r.status_code == 200 and r.json()["interlocuteurs"] == []


def test_stats_avancees_par_mois_et_usages():
    generer(None, utiliser_fixture=True)  # crée des générations + fichiers avec blocs
    s = db.stats_avancees()
    assert s["par_mois"] and s["par_mois"][-1]["etats"] >= 17
    usages = {u["usage"]: u["n"] for u in s["top_usages"]}
    assert "REFECTOIRE" in usages  # blocs des documents produits
