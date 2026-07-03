"""Base de connaissance SQLite auto-enrichissante (runtime/gb.db).

Chaque devis traité ENRICHIT la base sans rien écraser de ce qu'elle sait déjà :
- le client est reconnu par son N° client (ou sa raison sociale) ;
- ses interlocuteurs, chantiers, adresses et devis sont mémorisés et complétés ;
- un journal trace « ce que la base a appris » (nouveau client, nouveau contact…).

Modèle relationnel : clients ↔ interlocuteurs / chantiers / devis ↔ générations ↔ fichiers.
Pensé pour être lu/écrit demain par des agents IA et un contrôleur d'automatisation.
Aucune dépendance externe (sqlite3 = stdlib). Connexion par opération, mode WAL.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime

from app.config import RUNTIME_DIR

DB_PATH = RUNTIME_DIR / "gb.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  numero_client TEXT UNIQUE,
  raison_sociale TEXT NOT NULL,
  adresse TEXT, code_postal TEXT, ville TEXT,
  premiere_vue TEXT, derniere_vue TEXT,
  nb_devis INTEGER NOT NULL DEFAULT 0,
  nb_etats INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS interlocuteurs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  nom TEXT NOT NULL, premiere_vue TEXT, derniere_vue TEXT,
  UNIQUE(client_id, nom)
);
CREATE TABLE IF NOT EXISTS chantiers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  titre TEXT, adresse TEXT, code_postal TEXT, ville TEXT,
  premiere_vue TEXT, derniere_vue TEXT,
  UNIQUE(client_id, titre)
);
CREATE TABLE IF NOT EXISTS devis (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  numero_offre TEXT UNIQUE,
  client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL,
  chantier_id INTEGER REFERENCES chantiers(id) ON DELETE SET NULL,
  commercial TEXT, date_devis TEXT, premiere_vue TEXT
);
CREATE TABLE IF NOT EXISTS generations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  devis_id INTEGER REFERENCES devis(id) ON DELETE SET NULL,
  client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL,
  chantier_id INTEGER REFERENCES chantiers(id) ON DELETE SET NULL,
  horodatage TEXT NOT NULL, horodatage_aff TEXT NOT NULL,
  nb_etats INTEGER NOT NULL DEFAULT 0, nb_assembles INTEGER NOT NULL DEFAULT 0,
  nb_individuels INTEGER NOT NULL DEFAULT 0, nb_sanitaires INTEGER NOT NULL DEFAULT 0,
  nb_reconnus INTEGER NOT NULL DEFAULT 0, nb_non_reconnus INTEGER NOT NULL DEFAULT 0,
  job_id TEXT, zip_nom TEXT
);
CREATE TABLE IF NOT EXISTS fichiers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  generation_id INTEGER NOT NULL REFERENCES generations(id) ON DELETE CASCADE,
  nom TEXT NOT NULL, type_etat TEXT, bloc TEXT
);
CREATE TABLE IF NOT EXISTS parametres (
  cle TEXT PRIMARY KEY,
  valeur TEXT
);
CREATE TABLE IF NOT EXISTS utilisateurs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  identifiant TEXT NOT NULL UNIQUE COLLATE NOCASE,
  nom_affiche TEXT NOT NULL,
  hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'utilisateur',
  actif INTEGER NOT NULL DEFAULT 1,
  cree_le TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS journal (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  horodatage TEXT NOT NULL, horodatage_aff TEXT NOT NULL,
  type TEXT NOT NULL, libelle TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_gen_client ON generations(client_id);
CREATE INDEX IF NOT EXISTS idx_gen_horo ON generations(horodatage);
"""

_pret = False


@contextmanager
def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    cx = sqlite3.connect(DB_PATH)
    cx.row_factory = sqlite3.Row
    cx.execute("PRAGMA journal_mode=WAL")
    cx.execute("PRAGMA foreign_keys=ON")
    try:
        yield cx
        cx.commit()
    finally:
        cx.close()


def init_db() -> None:
    global _pret
    with _conn() as cx:
        cx.executescript(_SCHEMA)
        # Migration douce : ajoute chantier_id aux bases existantes.
        cols = [r["name"] for r in cx.execute("PRAGMA table_info(generations)")]
        if "chantier_id" not in cols:
            cx.execute("ALTER TABLE generations ADD COLUMN chantier_id INTEGER")
        # Migration douce : rattache le journal au client (purge RGPD ciblée, sans LIKE hasardeux).
        cols_j = [r["name"] for r in cx.execute("PRAGMA table_info(journal)")]
        if "client_id" not in cols_j:
            cx.execute("ALTER TABLE journal ADD COLUMN client_id INTEGER")
    _pret = True


def _ensure() -> None:
    if not _pret:
        init_db()


def _vide(v) -> bool:
    return v is None or str(v).strip() == ""


def lire_parametre(cle: str, defaut: str | None = None) -> str | None:
    """Paramètre d'application (marque blanche, préférences…)."""
    _ensure()
    with _conn() as cx:
        r = cx.execute("SELECT valeur FROM parametres WHERE cle=?", (cle,)).fetchone()
    return r["valeur"] if r else defaut


def ecrire_parametre(cle: str, valeur: str) -> None:
    _ensure()
    with _conn() as cx:
        cx.execute(
            "INSERT INTO parametres (cle, valeur) VALUES (?,?) "
            "ON CONFLICT(cle) DO UPDATE SET valeur=excluded.valeur",
            (cle, valeur),
        )


# --------------------------------------------------------------------------- #
# Comptes utilisateurs (multi-postes : authentification nominative + imputabilité)
# --------------------------------------------------------------------------- #
def lister_utilisateurs() -> list[dict]:
    """Comptes (sans les empreintes de mot de passe)."""
    _ensure()
    with _conn() as cx:
        rows = cx.execute(
            "SELECT id, identifiant, nom_affiche, role, actif, cree_le FROM utilisateurs "
            "ORDER BY identifiant"
        ).fetchall()
    return [dict(r) for r in rows]


def lire_utilisateur(identifiant: str) -> dict | None:
    """Compte actif correspondant à l'identifiant (avec hash, pour vérification)."""
    _ensure()
    with _conn() as cx:
        r = cx.execute(
            "SELECT * FROM utilisateurs WHERE identifiant = ? COLLATE NOCASE AND actif = 1",
            (identifiant,),
        ).fetchone()
    return dict(r) if r else None


def utilisateurs_actifs_existent() -> bool:
    _ensure()
    with _conn() as cx:
        return cx.execute("SELECT 1 FROM utilisateurs WHERE actif=1 LIMIT 1").fetchone() is not None


def creer_utilisateur(identifiant: str, nom_affiche: str, hash_: str, role: str) -> int:
    """Crée un compte. Lève ValueError si l'identifiant existe déjà."""
    _ensure()
    if role not in ("admin", "utilisateur"):
        raise ValueError("Rôle invalide (admin ou utilisateur).")
    iso = datetime.now().isoformat(timespec="seconds")
    with _conn() as cx:
        ex = cx.execute(
            "SELECT 1 FROM utilisateurs WHERE identifiant = ? COLLATE NOCASE", (identifiant,)
        ).fetchone()
        if ex:
            raise ValueError("Cet identifiant existe déjà.")
        cur = cx.execute(
            "INSERT INTO utilisateurs (identifiant, nom_affiche, hash, role, actif, cree_le) "
            "VALUES (?,?,?,?,1,?)",
            (identifiant, nom_affiche, hash_, role, iso),
        )
        return int(cur.lastrowid)


def modifier_utilisateur(uid: int, *, hash_: str | None = None, actif: bool | None = None) -> None:
    """Change le mot de passe et/ou l'état actif. Protège le dernier admin actif."""
    _ensure()
    with _conn() as cx:
        u = cx.execute("SELECT * FROM utilisateurs WHERE id=?", (uid,)).fetchone()
        if u is None:
            raise ValueError("Compte introuvable.")
        if actif is False and u["role"] == "admin":
            autres = cx.execute(
                "SELECT COUNT(*) n FROM utilisateurs WHERE role='admin' AND actif=1 AND id<>?", (uid,)
            ).fetchone()["n"]
            if autres == 0:
                raise ValueError("Impossible de désactiver le dernier administrateur actif.")
        if hash_ is not None:
            cx.execute("UPDATE utilisateurs SET hash=? WHERE id=?", (hash_, uid))
        if actif is not None:
            cx.execute("UPDATE utilisateurs SET actif=? WHERE id=?", (1 if actif else 0, uid))


def supprimer_client(client_id: int) -> list[str] | None:
    """Efface un client et TOUTES ses données personnelles (RGPD — droit à l'effacement).

    Supprime : fiche client, interlocuteurs et chantiers (cascade), devis, générations et
    fichiers associés, ainsi que les entrées de journal citant le client. Une trace minimale
    et anonyme (id seul) est conservée dans le journal.
    Renvoie la liste des job_id dont les dossiers de sortie sont à purger, ou None si inconnu.
    """
    _ensure()
    now = datetime.now()
    iso, aff = now.isoformat(timespec="seconds"), now.strftime("%d/%m/%Y · %H:%M")
    with _conn() as cx:
        client = cx.execute(
            "SELECT raison_sociale, numero_client FROM clients WHERE id=?", (client_id,)
        ).fetchone()
        if client is None:
            return None
        jobs = [
            r["job_id"]
            for r in cx.execute(
                "SELECT job_id FROM generations WHERE client_id=? AND job_id IS NOT NULL",
                (client_id,),
            )
        ]
        # Générations (les fichiers suivent en cascade) puis devis, puis la fiche
        # (interlocuteurs et chantiers suivent en cascade).
        cx.execute("DELETE FROM generations WHERE client_id=?", (client_id,))
        cx.execute("DELETE FROM devis WHERE client_id=?", (client_id,))
        cx.execute("DELETE FROM clients WHERE id=?", (client_id,))
        # Journal : purge ciblée par client_id ; le LIKE sur la raison sociale ne sert que pour
        # les anciennes entrées créées avant la colonne client_id (nom d'entreprise = long,
        # collision improbable ; surtout pas de LIKE sur le n° client, trop court).
        cx.execute("DELETE FROM journal WHERE client_id=?", (client_id,))
        cx.execute("DELETE FROM journal WHERE libelle LIKE ?", (f"%{client['raison_sociale']}%",))
        cx.execute(
            "INSERT INTO journal (horodatage, horodatage_aff, type, libelle) VALUES (?,?,?,?)",
            (iso, aff, "client_supprime", f"Client supprimé sur demande (RGPD) — fiche n° {client_id}"),
        )
    return jobs


def importer_client(
    *,
    raison_sociale: str = "",
    numero_client: str | None = None,
    commercial: str | None = None,  # non stocké au niveau client (info de devis)
    interlocuteur: str | None = None,
    adresse: str | None = None,
    code_postal: str | None = None,
    ville: str | None = None,
) -> str:
    """Crée ou enrichit un client (+ interlocuteur) depuis un import CSV.

    Reconnaissance par n° client puis raison sociale (comme l'enrichissement par devis).
    Renvoie « nouveau », « enrichi » ou « ignore ».
    """
    _ensure()
    if _vide(raison_sociale) and _vide(numero_client):
        return "ignore"
    iso = datetime.now().isoformat(timespec="seconds")
    with _conn() as cx:
        client = None
        if not _vide(numero_client):
            client = cx.execute(
                "SELECT id FROM clients WHERE numero_client = ?", (numero_client,)
            ).fetchone()
        if client is None and not _vide(raison_sociale):
            client = cx.execute(
                "SELECT id FROM clients WHERE raison_sociale = ? COLLATE NOCASE", (raison_sociale,)
            ).fetchone()
        if client is None:
            cur = cx.execute(
                """INSERT INTO clients
                   (numero_client, raison_sociale, adresse, code_postal, ville, premiere_vue, derniere_vue)
                   VALUES (?,?,?,?,?,?,?)""",
                (numero_client or None, raison_sociale or "—", adresse, code_postal, ville, iso, iso),
            )
            client_id = int(cur.lastrowid)
            statut = "nouveau"
        else:
            client_id = client["id"]
            cx.execute(
                """UPDATE clients SET
                     numero_client = COALESCE(NULLIF(numero_client,''), ?),
                     adresse       = COALESCE(NULLIF(adresse,''), ?),
                     code_postal   = COALESCE(NULLIF(code_postal,''), ?),
                     ville         = COALESCE(NULLIF(ville,''), ?),
                     derniere_vue  = ?
                   WHERE id = ?""",
                (numero_client, adresse, code_postal, ville, iso, client_id),
            )
            statut = "enrichi"
        if not _vide(interlocuteur):
            ex = cx.execute(
                "SELECT id FROM interlocuteurs WHERE client_id=? AND nom=? COLLATE NOCASE",
                (client_id, interlocuteur),
            ).fetchone()
            if ex is None:
                cx.execute(
                    "INSERT INTO interlocuteurs (client_id, nom, premiere_vue, derniere_vue) "
                    "VALUES (?,?,?,?)",
                    (client_id, interlocuteur, iso, iso),
                )
    return statut


# --------------------------------------------------------------------------- #
# Enrichissement : le cœur de la base qui apprend
# --------------------------------------------------------------------------- #
def enrichir_et_enregistrer(*, entete, counts, fichiers, job_id, zip_nom) -> dict:
    """Reconnaît/enrichit le client, ses contacts/chantiers/devis, enregistre la génération.

    Renvoie un résumé { client_id, devis_id, generation_id, appris: [libellés] }.
    """
    _ensure()
    now = datetime.now()
    iso, aff = now.isoformat(timespec="seconds"), now.strftime("%d/%m/%Y · %H:%M")
    appris: list[str] = []

    with _conn() as cx:
        def evt(type_, libelle, cid=None):
            # cid = client concerné : permet la purge RGPD ciblée du journal (voir supprimer_client).
            cx.execute(
                "INSERT INTO journal (horodatage, horodatage_aff, type, libelle, client_id) "
                "VALUES (?,?,?,?,?)",
                (iso, aff, type_, libelle, cid),
            )
            appris.append(libelle)

        # --- Client : reconnaissance par N° client puis raison sociale ---
        client = None
        if not _vide(entete.numero_client):
            client = cx.execute(
                "SELECT * FROM clients WHERE numero_client = ?", (entete.numero_client,)
            ).fetchone()
        if client is None and not _vide(entete.client):
            client = cx.execute(
                "SELECT * FROM clients WHERE raison_sociale = ? COLLATE NOCASE", (entete.client,)
            ).fetchone()

        if client is None:
            cur = cx.execute(
                """INSERT INTO clients
                   (numero_client, raison_sociale, adresse, code_postal, ville, premiere_vue, derniere_vue)
                   VALUES (?,?,?,?,?,?,?)""",
                (entete.numero_client, entete.client or "—", entete.adresse_client,
                 entete.code_postal_client, entete.ville_client, iso, iso),
            )
            client_id = int(cur.lastrowid)
            evt("client_nouveau", f"Nouveau client : {entete.client or '—'}"
                + (f" (n° {entete.numero_client})" if not _vide(entete.numero_client) else ""),
                cid=client_id)
        else:
            client_id = client["id"]
            # Enrichit les champs manquants SANS écraser l'existant.
            avant = (client["adresse"], client["code_postal"], client["ville"], client["numero_client"])
            cx.execute(
                """UPDATE clients SET
                     numero_client = COALESCE(NULLIF(numero_client,''), ?),
                     adresse       = COALESCE(NULLIF(adresse,''), ?),
                     code_postal   = COALESCE(NULLIF(code_postal,''), ?),
                     ville         = COALESCE(NULLIF(ville,''), ?),
                     derniere_vue  = ?
                   WHERE id = ?""",
                (entete.numero_client, entete.adresse_client, entete.code_postal_client,
                 entete.ville_client, iso, client_id),
            )
            apres = cx.execute(
                "SELECT adresse, code_postal, ville, numero_client FROM clients WHERE id=?", (client_id,)
            ).fetchone()
            if tuple(apres) != avant:
                evt("client_enrichi", f"Fiche client complétée : {entete.client or '—'}", cid=client_id)

        # --- Interlocuteur ---
        if not _vide(entete.interlocuteur):
            ex = cx.execute(
                "SELECT id FROM interlocuteurs WHERE client_id=? AND nom=? COLLATE NOCASE",
                (client_id, entete.interlocuteur),
            ).fetchone()
            if ex is None:
                cx.execute(
                    "INSERT INTO interlocuteurs (client_id, nom, premiere_vue, derniere_vue) VALUES (?,?,?,?)",
                    (client_id, entete.interlocuteur, iso, iso),
                )
                evt("contact_nouveau", f"Nouveau contact : {entete.interlocuteur} ({entete.client})",
                    cid=client_id)
            else:
                cx.execute("UPDATE interlocuteurs SET derniere_vue=? WHERE id=?", (iso, ex["id"]))

        # --- Chantier ---
        chantier_id = None
        if not _vide(entete.titre_chantier):
            ex = cx.execute(
                "SELECT id FROM chantiers WHERE client_id=? AND titre=? COLLATE NOCASE",
                (client_id, entete.titre_chantier),
            ).fetchone()
            if ex is None:
                cur = cx.execute(
                    """INSERT INTO chantiers (client_id, titre, adresse, code_postal, ville, premiere_vue, derniere_vue)
                       VALUES (?,?,?,?,?,?,?)""",
                    (client_id, entete.titre_chantier, entete.adresse, entete.code_postal, entete.ville, iso, iso),
                )
                chantier_id = int(cur.lastrowid)
                evt("chantier_nouveau", f"Nouveau chantier : {entete.titre_chantier} ({entete.client})",
                    cid=client_id)
            else:
                chantier_id = ex["id"]
                cx.execute("UPDATE chantiers SET derniere_vue=? WHERE id=?", (iso, chantier_id))

        # --- Devis ---
        devis_id = None
        if not _vide(entete.numero_offre):
            ex = cx.execute("SELECT id FROM devis WHERE numero_offre=?", (entete.numero_offre,)).fetchone()
            if ex is None:
                cur = cx.execute(
                    """INSERT INTO devis (numero_offre, client_id, chantier_id, commercial, date_devis, premiere_vue)
                       VALUES (?,?,?,?,?,?)""",
                    (entete.numero_offre, client_id, chantier_id, entete.commercial, entete.date_devis, iso),
                )
                devis_id = int(cur.lastrowid)
                evt("devis_nouveau", f"Devis enregistré : {entete.numero_offre} ({entete.client})",
                    cid=client_id)
            else:
                devis_id = ex["id"]
                cx.execute(
                    """UPDATE devis SET client_id=COALESCE(client_id,?), chantier_id=COALESCE(chantier_id,?),
                         commercial=COALESCE(NULLIF(commercial,''),?), date_devis=COALESCE(NULLIF(date_devis,''),?)
                       WHERE id=?""",
                    (client_id, chantier_id, entete.commercial, entete.date_devis, devis_id),
                )

        # --- Génération + fichiers ---
        cur = cx.execute(
            """INSERT INTO generations
               (devis_id, client_id, chantier_id, horodatage, horodatage_aff, nb_etats, nb_assembles,
                nb_individuels, nb_sanitaires, nb_reconnus, nb_non_reconnus, job_id, zip_nom)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (devis_id, client_id, chantier_id, iso, aff, counts["etats"], counts["assembles"],
             counts["individuels"], counts["sanitaires"], counts["individuels"] + counts["sanitaires"],
             counts["non_reconnus"], job_id, zip_nom),
        )
        generation_id = int(cur.lastrowid)
        cx.executemany(
            "INSERT INTO fichiers (generation_id, nom, type_etat, bloc) VALUES (?,?,?,?)",
            [(generation_id, f["nom"], f.get("type"), f.get("bloc")) for f in fichiers],
        )

        # --- Recalcule les agrégats du client ---
        cx.execute(
            """UPDATE clients SET
                 nb_devis = (SELECT COUNT(*) FROM devis WHERE client_id=?),
                 nb_etats = (SELECT COALESCE(SUM(nb_etats),0) FROM generations WHERE client_id=?)
               WHERE id=?""",
            (client_id, client_id, client_id),
        )

    return {"client_id": client_id, "devis_id": devis_id, "generation_id": generation_id, "appris": appris}


# --------------------------------------------------------------------------- #
# Lectures
# --------------------------------------------------------------------------- #
_RECENT = """
SELECT g.id, d.numero_offre AS offre, c.raison_sociale AS client, c.numero_client,
       ch.titre AS chantier, g.nb_etats AS etats, g.nb_assembles AS assembles,
       g.nb_sanitaires AS sanitaires, g.horodatage_aff AS horodatage, g.job_id, g.zip_nom
FROM generations g
LEFT JOIN devis d ON d.id = g.devis_id
LEFT JOIN clients c ON c.id = g.client_id
LEFT JOIN chantiers ch ON ch.id = d.chantier_id
"""


def dashboard() -> dict:
    """Agrégats globaux + clients connus + 20 dernières générations + journal récent."""
    _ensure()
    with _conn() as cx:
        r = cx.execute(
            """SELECT COUNT(*) g, COALESCE(SUM(nb_etats),0) e, COALESCE(SUM(nb_assembles),0) a,
               COALESCE(SUM(nb_individuels),0) i, COALESCE(SUM(nb_sanitaires),0) s,
               COALESCE(SUM(nb_reconnus),0) r, COALESCE(SUM(nb_non_reconnus),0) nr FROM generations"""
        ).fetchone()
        nb_clients = cx.execute("SELECT COUNT(*) n FROM clients").fetchone()["n"]
        nb_devis = cx.execute("SELECT COUNT(*) n FROM devis").fetchone()["n"]
        recents = cx.execute(_RECENT + " ORDER BY g.id DESC LIMIT 20").fetchall()
        appris = cx.execute(
            "SELECT type, libelle, horodatage_aff FROM journal ORDER BY id DESC LIMIT 8"
        ).fetchall()
    base = r["r"] + r["nr"]
    return {
        "total_generations": r["g"], "total_etats": r["e"], "total_assembles": r["a"],
        "total_individuels": r["i"], "total_sanitaires": r["s"],
        "total_reconnus": r["r"], "total_non_reconnus": r["nr"],
        "nb_clients": nb_clients, "nb_devis": nb_devis,
        "taux_reconnaissance": round(100 * r["r"] / base) if base else None,
        "historique": [dict(x) for x in recents],
        "appris": [dict(x) for x in appris],
    }


def lister_historique(q: str | None = None, limit: int = 200, offset: int = 0) -> list[dict]:
    _ensure()
    sql = _RECENT
    params: list = []
    if q:
        sql += " WHERE c.raison_sociale LIKE ? OR d.numero_offre LIKE ? OR ch.titre LIKE ? OR c.numero_client LIKE ?"
        like = f"%{q}%"
        params += [like, like, like, like]
    sql += " ORDER BY g.id DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    with _conn() as cx:
        return [dict(r) for r in cx.execute(sql, params).fetchall()]


def lister_clients() -> list[dict]:
    _ensure()
    with _conn() as cx:
        rows = cx.execute(
            """SELECT c.*,
                 (SELECT COUNT(*) FROM interlocuteurs WHERE client_id=c.id) AS nb_contacts,
                 (SELECT COUNT(*) FROM chantiers WHERE client_id=c.id) AS nb_chantiers
               FROM clients c ORDER BY c.derniere_vue DESC"""
        ).fetchall()
    return [dict(r) for r in rows]


def lire_client(client_id: int) -> dict | None:
    _ensure()
    with _conn() as cx:
        c = cx.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
        if not c:
            return None
        contacts = cx.execute(
            "SELECT nom, derniere_vue FROM interlocuteurs WHERE client_id=? ORDER BY nom", (client_id,)
        ).fetchall()
        # Chantiers du client, CLASSÉS PAR NOM, avec leurs compteurs.
        chantiers = cx.execute(
            """SELECT ch.id, ch.titre, ch.adresse, ch.code_postal, ch.ville,
                 (SELECT COUNT(*) FROM devis WHERE chantier_id=ch.id) AS nb_devis,
                 (SELECT COALESCE(SUM(nb_etats),0) FROM generations WHERE chantier_id=ch.id) AS nb_etats
               FROM chantiers ch WHERE ch.client_id=? ORDER BY ch.titre COLLATE NOCASE""",
            (client_id,),
        ).fetchall()
        devis = cx.execute(
            "SELECT numero_offre, commercial, date_devis FROM devis WHERE client_id=? ORDER BY id DESC",
            (client_id,),
        ).fetchall()
    d = dict(c)
    d["interlocuteurs"] = [dict(x) for x in contacts]
    d["chantiers"] = [dict(x) for x in chantiers]
    d["devis"] = [dict(x) for x in devis]
    return d


def lire_chantier(chantier_id: int) -> dict | None:
    """Contenu complet d'un chantier : client, devis, états des lieux (fichiers), historique."""
    _ensure()
    with _conn() as cx:
        ch = cx.execute("SELECT * FROM chantiers WHERE id=?", (chantier_id,)).fetchone()
        if not ch:
            return None
        client = cx.execute(
            "SELECT id, raison_sociale, numero_client FROM clients WHERE id=?", (ch["client_id"],)
        ).fetchone()
        devis = cx.execute(
            "SELECT numero_offre, commercial, date_devis FROM devis WHERE chantier_id=? ORDER BY id DESC",
            (chantier_id,),
        ).fetchall()
        gens = cx.execute(
            """SELECT g.id, g.nb_etats AS etats, g.horodatage_aff AS horodatage, g.job_id, g.zip_nom,
                 (SELECT numero_offre FROM devis WHERE devis.id = g.devis_id) AS offre
               FROM generations g WHERE g.chantier_id=? ORDER BY g.id DESC""",
            (chantier_id,),
        ).fetchall()
        generations = []
        for g in gens:
            fics = cx.execute(
                "SELECT nom, type_etat, bloc FROM fichiers WHERE generation_id=? ORDER BY id", (g["id"],)
            ).fetchall()
            gg = dict(g)
            gg["fichiers"] = [dict(f) for f in fics]
            generations.append(gg)
    d = dict(ch)
    d["client"] = dict(client) if client else None
    d["devis"] = [dict(x) for x in devis]
    d["generations"] = generations
    return d


def stats_avancees() -> dict:
    _ensure()
    with _conn() as cx:
        serie = cx.execute(
            """SELECT substr(horodatage,1,10) AS jour, COUNT(*) AS generations, COALESCE(SUM(nb_etats),0) AS etats
               FROM generations GROUP BY jour ORDER BY jour DESC LIMIT 30"""
        ).fetchall()
        top = cx.execute(
            """SELECT raison_sociale AS client, nb_devis AS devis, nb_etats AS etats FROM clients
               WHERE nb_etats > 0 ORDER BY nb_etats DESC LIMIT 8"""
        ).fetchall()
        t = cx.execute(
            """SELECT COALESCE(SUM(nb_assembles),0) a, COALESCE(SUM(nb_individuels),0) i,
               COALESCE(SUM(nb_sanitaires),0) s, COALESCE(SUM(nb_non_reconnus),0) nr FROM generations"""
        ).fetchone()
    return {
        "serie": [dict(r) for r in reversed(serie)],
        "top_clients": [dict(r) for r in top],
        "types": {"assembles": t["a"], "individuels": t["i"], "sanitaires": t["s"], "non_reconnus": t["nr"]},
    }
