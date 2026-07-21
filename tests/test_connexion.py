"""Connexion « pro » : page + session cookie, chemins publics, proxy, preuve de signature, SMTP."""

import shutil
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from app import courriel, db, terrain
from app.config import get_reglages
from app.main import app
from app.securite import COOKIE_SESSION, creer_session, hacher, ip_client, valider_session

MODELE = Path(__file__).parent.parent / "templates" / "bungalow_vide.xlsx"
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d4944415478da63fcffff3f030005fe02fea72d34490000000049454e44ae426082"
)


def _comptes():
    db.creer_utilisateur("admin", "Admin", hacher("motdepasse8"), "admin")
    db.creer_utilisateur("chauffeur1", "Karim", hacher("motdepasse8"), "chauffeur")


# ------------------------------------------------------------------ connexion

def test_connexion_pose_le_cookie_et_ouvre_la_session():
    _comptes()
    tc = TestClient(app)
    r = tc.post("/connexion", json={"identifiant": "admin", "mot_de_passe": "motdepasse8"})
    assert r.status_code == 200 and r.json()["role"] == "admin"
    assert COOKIE_SESSION in tc.cookies
    # Le cookie suffit désormais (pas d'auth Basic).
    e = tc.get("/etat")
    assert e.status_code == 200 and e.json()["utilisateur"] == "admin"


def test_connexion_mauvais_mot_de_passe():
    _comptes()
    r = TestClient(app).post("/connexion", json={"identifiant": "admin", "mot_de_passe": "faux"})
    assert r.status_code == 401


def test_accueil_redirige_vers_la_page_de_connexion():
    _comptes()
    r = TestClient(app).get("/", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "/connexion"


def test_page_connexion_publique_et_marquee():
    _comptes()
    db.ecrire_parametre("societe", "Ma Société")
    r = TestClient(app).get("/connexion")
    assert r.status_code == 200 and "Ma Société" in r.text


def test_manifest_et_service_worker_publics():
    _comptes()
    tc = TestClient(app)
    assert tc.get("/manifest.json").status_code == 200
    sw = tc.get("/sw.js")
    assert sw.status_code == 200 and "gb-" in sw.text


def test_deconnexion_ferme_la_session():
    _comptes()
    tc = TestClient(app)
    tc.post("/connexion", json={"identifiant": "admin", "mot_de_passe": "motdepasse8"})
    tc.post("/deconnexion")
    assert tc.get("/etat").status_code == 401


def test_session_chauffeur_reste_cloisonnee():
    _comptes()
    tc = TestClient(app)
    tc.post("/connexion", json={"identifiant": "chauffeur1", "mot_de_passe": "motdepasse8"})
    assert tc.get("/constats").status_code == 200
    assert tc.get("/clients").status_code == 403


def test_session_falsifiee_refusee():
    _comptes()
    assert valider_session("abc.123.deadbeef") is None
    jeton = creer_session("admin")
    assert valider_session(jeton) == ("admin", "admin")
    assert valider_session(jeton[:-2] + "00") is None


def test_session_compte_desactive_refusee():
    uid = db.creer_utilisateur("x", "X", hacher("motdepasse8"), "admin")
    db.creer_utilisateur("y", "Y", hacher("motdepasse8"), "admin")
    jeton = creer_session("x")
    db.modifier_utilisateur(uid, actif=False)
    assert valider_session(jeton) is None


# ---------------------------------------------------------------- proxy / IP

class _Req:
    def __init__(self, entetes, hote="10.0.0.9"):
        self.headers = entetes
        self.client = type("C", (), {"host": hote})()


def test_ip_client_ignore_les_entetes_sans_proxy_de_confiance(monkeypatch):
    monkeypatch.setenv("GB_PROXY_CONFIANCE", "0")
    get_reglages.cache_clear()
    assert ip_client(_Req({"CF-Connecting-IP": "1.2.3.4"})) == "10.0.0.9"


def test_ip_client_lit_les_entetes_derriere_proxy(monkeypatch):
    monkeypatch.setenv("GB_PROXY_CONFIANCE", "1")
    get_reglages.cache_clear()
    assert ip_client(_Req({"CF-Connecting-IP": "1.2.3.4"})) == "1.2.3.4"
    assert ip_client(_Req({"X-Forwarded-For": "5.6.7.8, 9.9.9.9"})) == "5.6.7.8"
    get_reglages.cache_clear()


# ------------------------------------------------- preuve de signature

def test_signature_construit_le_dossier_de_preuve(tmp_path):
    doc = tmp_path / "etat.xlsx"
    shutil.copy(MODELE, doc)
    dossier = tmp_path / "constat"
    dossier.mkdir()
    empreinte = terrain.enregistrer_signature(
        dossier, PNG, "M. Client", document=doc, fonction="Chef de chantier"
    )
    assert empreinte and len(empreinte) == 64
    import hashlib
    import json

    # L'empreinte correspond exactement au fichier signé (signature incluse).
    assert empreinte == hashlib.sha256(doc.read_bytes()).hexdigest()
    with zipfile.ZipFile(doc) as z:
        assert "xl/media/signature_gb.png" in z.namelist()
    data = json.loads((dossier / "constat.json").read_text(encoding="utf-8"))
    assert data["fonction"] == "Chef de chantier"
    assert data["empreinte_sha256"] == empreinte
    assert data["signe_le_iso"]


def test_journaliser_trace_l_evenement():
    db.init_db()
    db.journaliser("signature", "Constat signé : test.xlsx")
    stats = db.dashboard()
    assert any("Constat signé" in j["libelle"] for j in stats["appris"])


# ------------------------------------------------------------------- e-mail

def test_smtp_reserve_aux_admins_et_sans_fuite_du_mot_de_passe():
    _comptes()
    tc = TestClient(app)
    assert tc.get("/parametres/smtp", auth=("chauffeur1", "motdepasse8")).status_code == 403
    r = tc.post(
        "/parametres/smtp",
        json={"hote": "smtp.exemple.fr", "port": "587", "securite": "tls",
              "utilisateur": "u@exemple.fr", "expediteur": "edl@exemple.fr", "mdp": "secret"},
        auth=("admin", "motdepasse8"),
    )
    assert r.status_code == 200
    d = r.json()
    assert d["configure"] is True and "secret" not in str(d)
    # Un enregistrement sans mot de passe conserve l'existant.
    courriel.enregistrer({"hote": "smtp.exemple.fr"})
    assert db.lire_parametre("smtp_mdp") == "secret"


def test_envoi_constat_exige_configuration_et_adresse():
    _comptes()
    tc = TestClient(app)
    tc.post("/connexion", json={"identifiant": "chauffeur1", "mot_de_passe": "motdepasse8"})
    r = tc.post("/terrain/job-inconnu/x.xlsx/envoyer", json={"destinataire": "pas-un-email"})
    assert r.status_code == 400


# --------------------------------------------------------------- accès distant

def test_adresse_publique_enregistree_et_dans_le_qr():
    _comptes()
    tc = TestClient(app)
    auth = ("admin", "motdepasse8")
    assert tc.post("/mobile-adresse", json={"adresse": "ftp://mauvais"}, auth=auth).status_code == 400
    r = tc.post("/mobile-adresse", json={"adresse": "https://app.gb-location.fr/"}, auth=auth)
    assert r.status_code == 200 and r.json()["adresse_publique"] == "https://app.gb-location.fr"
    infos = tc.get("/mobile-infos", auth=auth).json()
    assert infos["adresse_publique"] == "https://app.gb-location.fr"
    qr = tc.get("/mobile-qr", auth=auth)
    assert qr.status_code == 200 and "svg" in qr.headers["content-type"]
