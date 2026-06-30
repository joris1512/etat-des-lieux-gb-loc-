"""Régressions de robustesse de la génération (en-tête incomplet, etc.)."""

from fastapi.testclient import TestClient

from app.main import app


def test_generer_revise_entete_chantier_vide_ne_422_pas():
    """Régression : un en-tête de chantier vide (ce que l'UI envoie quand un champ est
    laissé vide) ne doit PAS provoquer un 422 ; la génération doit aboutir."""
    client = TestClient(app)
    payload = {
        "entete": {
            "client": "ACME",
            "titre_chantier": "",
            "adresse": "",
            "code_postal": "",
            "ville": "",
        },
        "articles": [
            {
                "texte_ligne": "BUNGALOW 15m2 BATISO",
                "bloc": "VESTIAIRE",
                "est_bungalow": True,
                "quantite": 1,
                "mobilier": [],
            }
        ],
    }
    r = client.post("/generer-revise", json=payload)
    assert r.status_code == 200, r.text
    assert len(r.json()["fichiers"]) == 1
