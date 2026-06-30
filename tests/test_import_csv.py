"""Import CSV d'une base clients : parsing souple + enrichissement (dédoublonnage)."""

import pytest
from fastapi.testclient import TestClient

from app import db, import_csv
from app.main import app

CSV = (
    "Ag;Bon;Raison sociale;Client;Cial;Interlocuteur\n"
    "GB1;1;ACME SARL - PARIS;1234;CBO;M. DUPONT\n"
    "GB1;2;ACME SARL - PARIS;1234;CBO;M. DUPONT\n"  # même client -> enrichi, pas de doublon
    "GB1;3;BETA SAS - LYON;5678;CH;Mme MARTIN\n"
).encode("utf-8")


def test_parser_mappe_les_colonnes():
    lignes = import_csv.parser(CSV)
    assert len(lignes) == 3
    assert lignes[0]["raison_sociale"] == "ACME SARL - PARIS"
    assert lignes[0]["numero_client"] == "1234"
    assert lignes[0]["interlocuteur"] == "M. DUPONT"


def test_parser_detecte_virgule_et_encodage():
    contenu = "Raison sociale,Client\nSOCIÉTÉ É,9\n".encode("cp1252")
    lignes = import_csv.parser(contenu)
    assert lignes[0]["numero_client"] == "9"
    assert "SOCI" in lignes[0]["raison_sociale"]


def test_parser_refuse_sans_colonne_reconnue():
    with pytest.raises(ValueError):
        import_csv.parser(b"Foo;Bar\n1;2\n")


def test_import_cree_et_dedoublonne():
    for ligne in import_csv.parser(CSV):
        db.importer_client(**ligne)
    nums = [c["numero_client"] for c in db.lister_clients()]
    assert nums.count("1234") == 1  # le doublon n'a pas créé deux fiches
    assert "5678" in nums


def test_endpoint_importer_csv():
    client = TestClient(app)
    r = client.post("/clients/importer-csv", files={"fichier": ("base.csv", CSV, "text/csv")})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 3
    assert data["nouveaux"] == 2 and data["enrichis"] == 1
