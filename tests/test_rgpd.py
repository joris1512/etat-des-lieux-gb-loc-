"""RGPD — droit à l'effacement : suppression complète d'un client (base + fichiers + journal)."""

from fastapi.testclient import TestClient

from app import db, generation
from app.extraction import charger_fixture
from app.generation import generer
from app.main import app


def _generer_dossier_eiffage():
    rapport, job_dir = generer(None, utiliser_fixture=True)
    assert rapport.fichiers
    return rapport, job_dir


def test_suppression_client_efface_base_et_fichiers():
    _rapport, job_dir = _generer_dossier_eiffage()
    client = next(c for c in db.lister_clients() if "EIFFAGE" in c["raison_sociale"])

    jobs = db.supprimer_client(client["id"])
    assert jobs and job_dir.name in jobs

    # Plus aucune trace nominative en base.
    assert all(c["id"] != client["id"] for c in db.lister_clients())
    assert not db.lire_client(client["id"])


def test_suppression_purge_le_journal_nominatif():
    _generer_dossier_eiffage()
    client = next(c for c in db.lister_clients() if "EIFFAGE" in c["raison_sociale"])
    db.supprimer_client(client["id"])
    libelles = [e["libelle"] for e in db.dashboard()["appris"]]
    assert not any("EIFFAGE" in x for x in libelles)
    # Une trace anonyme (id seul) est conservée.
    assert any("RGPD" in x for x in libelles)


def test_endpoint_delete_client_purge_les_dossiers():
    _rapport, job_dir = _generer_dossier_eiffage()
    client = next(c for c in db.lister_clients() if "EIFFAGE" in c["raison_sociale"])
    assert job_dir.exists()

    tc = TestClient(app)
    # L'endpoint purge sous SORTIES_DIR patché par conftest (module generation = module main).
    import app.main as main_mod

    ancien = main_mod.SORTIES_DIR
    main_mod.SORTIES_DIR = generation.SORTIES_DIR
    try:
        r = tc.delete(f"/clients/{client['id']}")
    finally:
        main_mod.SORTIES_DIR = ancien
    assert r.status_code == 200
    assert r.json()["supprime"] is True
    assert not job_dir.exists()  # les documents (nom du client dans le fichier) sont effacés


def test_endpoint_delete_client_introuvable_404():
    tc = TestClient(app)
    assert tc.delete("/clients/999999").status_code == 404


def test_suppression_conserve_les_autres_clients():
    _generer_dossier_eiffage()
    db.importer_client(raison_sociale="AUTRE SOCIETE", numero_client="42")
    client = next(c for c in db.lister_clients() if "EIFFAGE" in c["raison_sociale"])
    db.supprimer_client(client["id"])
    restants = [c["raison_sociale"] for c in db.lister_clients()]
    assert "AUTRE SOCIETE" in restants


def test_purge_journal_ciblee_epargne_les_autres_clients():
    """Régression : la purge du journal ne doit pas sur-effacer (ex. n° client court « 7 »)."""
    db.importer_client(raison_sociale="CIBLE A EFFACER SARL", numero_client="7")
    db.importer_client(raison_sociale="TIERS INNOCENT SAS", numero_client="77")
    ids = {c["raison_sociale"]: c["id"] for c in db.lister_clients()}
    with db._conn() as cx:
        cx.execute(
            "INSERT INTO journal (horodatage, horodatage_aff, type, libelle, client_id) "
            "VALUES ('t','t','x','Entrée du client cible', ?)",
            (ids["CIBLE A EFFACER SARL"],),
        )
        cx.execute(
            "INSERT INTO journal (horodatage, horodatage_aff, type, libelle, client_id) "
            "VALUES ('t','t','x','Note 7 chantiers pour TIERS INNOCENT SAS', ?)",
            (ids["TIERS INNOCENT SAS"],),
        )
    db.supprimer_client(ids["CIBLE A EFFACER SARL"])
    with db._conn() as cx:
        restants = [r["libelle"] for r in cx.execute("SELECT libelle FROM journal")]
    assert not any("cible" in x.lower() for x in restants)
    # L'entrée du tiers (qui contient pourtant « 7 ») est intacte : plus de LIKE sur le n°.
    assert any("TIERS INNOCENT" in x for x in restants)


def test_fixture_eiffage_intacte():
    """Garde-fou : la fixture de démo n'est pas touchée par les tests d'effacement."""
    assert charger_fixture().entete.client == "EIFFAGE TRX MARITIMES FLUVIAUX"
