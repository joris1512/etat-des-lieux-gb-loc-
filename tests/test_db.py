"""Tests de la base de connaissance auto-enrichissante."""

import pytest

from app import db
from app.models import EnteteDevis


@pytest.fixture
def base(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    db._pret = False
    db.init_db()
    yield
    db._pret = False


def _ent(**kw):
    base = dict(
        client="ACME", numero_client="C1", interlocuteur="M. X", commercial="Y",
        adresse_client="1 rue", code_postal_client="40000", ville_client="DAX",
        numero_offre="D1", date_devis="01/01/2026",
        titre_chantier="CH1", adresse="2 rue", code_postal="40100", ville="SEIGNOSSE",
    )
    base.update(kw)
    return EnteteDevis(**base)


def _enr(ent, **counts):
    c = dict(etats=5, assembles=1, individuels=3, sanitaires=1, non_reconnus=0)
    c.update(counts)
    return db.enrichir_et_enregistrer(
        entete=ent, counts=c,
        fichiers=[{"nom": "a.xlsx", "type": "assemble", "bloc": "X"}],
        job_id="job1", zip_nom="z.zip",
    )


def test_meme_client_pas_duplique(base):
    _enr(_ent(numero_offre="D1"))
    _enr(_ent(numero_offre="D2"))  # même client C1, autre devis
    clients = db.lister_clients()
    assert len(clients) == 1
    assert clients[0]["nb_devis"] == 2
    assert clients[0]["nb_etats"] == 10


def test_reconnaissance_par_numero_client(base):
    _enr(_ent(client="ACME", numero_client="C1", numero_offre="D1"))
    _enr(_ent(client="ACME SARL", numero_client="C1", numero_offre="D2"))  # raison ≠, n° identique
    assert len(db.lister_clients()) == 1


def test_enrichit_sans_ecraser(base):
    _enr(_ent(adresse_client="1 rue de la Paix"))
    _enr(_ent(adresse_client="AUTRE ADRESSE", numero_offre="D2"))
    c = db.lire_client(db.lister_clients()[0]["id"])
    assert c["adresse"] == "1 rue de la Paix"  # l'existant n'est pas écrasé


def test_complete_un_champ_manquant(base):
    _enr(_ent(adresse_client=""))                       # client sans adresse au départ
    _enr(_ent(adresse_client="1 rue", numero_offre="D2"))  # 2e devis apporte l'adresse
    c = db.lire_client(db.lister_clients()[0]["id"])
    assert c["adresse"] == "1 rue"


def test_contacts_et_chantiers_cumules(base):
    _enr(_ent(interlocuteur="M. X", titre_chantier="CH1"))
    _enr(_ent(interlocuteur="Mme Y", titre_chantier="CH2", numero_offre="D2"))
    c = db.lire_client(db.lister_clients()[0]["id"])
    assert {i["nom"] for i in c["interlocuteurs"]} == {"M. X", "Mme Y"}
    assert {ch["titre"] for ch in c["chantiers"]} == {"CH1", "CH2"}


def test_recherche_historique(base):
    _enr(_ent(client="EIFFAGE", numero_client="E1", numero_offre="D1"))
    _enr(_ent(client="BOUYGUES", numero_client="B1", numero_offre="D2"))
    assert len(db.lister_historique("EIFF")) == 1
    assert len(db.lister_historique()) == 2


def test_journal_apprend(base):
    res = _enr(_ent())
    libelles = " ".join(res["appris"])
    assert "Nouveau client" in libelles
    assert "Nouveau contact" in libelles
    assert "Devis enregistré" in libelles
