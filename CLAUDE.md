# GB Location — Pré-remplissage des états des lieux (contexte projet)

> Ce fichier est lu automatiquement par Claude Code. Il sert à **reprendre le travail** sur une
> autre machine sans perdre le contexte. Voir aussi `README.md` (utilisateur), `HANDOFF.md`
> (reprise), `DEPLOIEMENT_WINDOWS.md` (serveur), `INTEGRATION_MISTRAL.md` (étude CRM).

## But
Outil interne pour **GB Location** (loueur de modulaires préfabriqués). À partir d'un **devis PDF**,
l'app reconnaît chaque module, choisit le bon **modèle Excel**, applique la **logique d'assemblage**,
**pré-remplit** l'en-tête + le mobilier, produit **un .xlsx par état + un ZIP**, et **enrichit une base
de connaissance** (clients / chantiers / devis) qui apprend à chaque devis.

## Stack & conventions (à respecter)
- **Python 3.12+** (développé en 3.14). **FastAPI + uvicorn**, **openpyxl**, **pydantic /
  pydantic-settings**, **sqlite3** (stdlib). Pas de dépendance lourde inutile.
- **100% cross-platform** : chemins via `pathlib`, rien d'Unix-only (déploiement serveur Windows).
- **Nommage et UI en français** (fonctions, commentaires, libellés).
- **Extraction du devis** = API Anthropic (bloc document base64) → JSON validé Pydantic.
  Modèle par défaut `claude-opus-4-8` (surcharge `GB_MODEL`). Mode **fixture** pour la démo hors-ligne.
- **Secrets dans `.env`** (gitignoré) : `ANTHROPIC_API_KEY` (requis pour l'extraction réelle).
  Auth optionnelle : `GB_PASSWORD` ou `GB_PASSWORD_HASH` (voir Sécurité).
- **Tests** : `pytest -q` doit rester **vert** ; `ruff check app scripts tests` doit rester **clean**.
  Les tests sont **isolés** (`tests/conftest.py` : base + sorties temporaires, pas de pollution du runtime).
- Après chaque changement notable : relancer tests + ruff. Vérifier l'UI via le serveur si pertinent.

## Lancer / tester
```bash
# Installer (1re fois)
python -m venv .venv && .venv/bin/pip install -r requirements.txt   # Windows : py -3.12 -m venv .venv ; .venv\Scripts\pip ...
cp .env.example .env        # renseigner ANTHROPIC_API_KEY (+ GB_PASSWORD si souhaité)
python scripts/make_placeholder_templates.py   # modèles factices tant que les vrais ne sont pas là
python scripts/seed_demo.py                     # (option) crée le dossier client EIFFAGE de démo

# Lancer
.venv/bin/python -m uvicorn app.main:app --port 8000     # Windows : scripts\run_prod.bat
#  -> http://localhost:8000

# Vérifier
.venv/bin/python -m pytest -q
.venv/bin/ruff check app scripts tests
```

## Architecture
```
app/
  config.py          Réglages .env + chemins
  models.py          Schémas Pydantic (extraction + plan)
  extraction.py      Devis PDF -> JSON (API Anthropic) + fixture démo
  correspondance.py  Normalisation texte + table texte->modèle + filtre prestations
  assemblage.py      Logique d'assemblage -> liste d'états
  remplissage.py     Écriture openpyxl (en-tête + mobilier)
  generation.py      analyser() / generer() / generer_depuis_extraction()  (+ archive + enrichissement)
  db.py              Base SQLite auto-enrichissante (clients/interlocuteurs/chantiers/devis/generations/fichiers/journal)
  modeles.py         Bibliothèque de modèles (lister/téléverser/supprimer, anti zip-bomb)
  purge.py           Purge des sorties (rétention ~1 an pour garder l'historique re-téléchargeable)
  securite.py        Auth HTTP Basic renforcée (hachage PBKDF2, anti-force-brute, audit)
  main.py            FastAPI : routes + middlewares (taille, en-têtes sécurité) + UI
  templates_html/index.html   Cockpit (UI sombre aux couleurs GB, mono-page)
  static/logo.png    Logo GB
config/cellules.yaml Cellules d'en-tête + mobilier par modèle  (À CALER sur les vrais .xlsx)
correspondances.csv  Table texte de devis -> fichier modèle      (À COMPLÉTER : ~25 entrées)
templates/           Modèles Excel (.xlsx)                        (À REMPLACER par les vrais)
fixtures/            Extraction pré-calculée du devis EIFFAGE (démo)
scripts/             install/run Windows, service, diagnostic, hash_password, seed_demo, modèles factices
tests/               pytest (isolés via conftest.py)
```
Routes clés : `/` (UI), `/analyser`, `/generer`, `/generer-revise`, `/telecharger/{job}/{nom}`,
`/modeles` (GET/POST/DELETE), `/stats`, `/historique`, `/clients`, `/clients/{id}`, `/chantiers/{id}`,
`/stats/avancees`, `/etat`.

## Sécurité (en place)
- Auth activée si `GB_PASSWORD` **ou** `GB_PASSWORD_HASH` défini. Hash recommandé :
  `python scripts/hash_password.py` → coller `GB_PASSWORD_HASH=...` dans `.env`.
- Anti-force-brute (blocage 429 après 8 échecs/IP), comparaison à temps constant, journal d'audit.
- En-têtes HTTP : CSP restrictive, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`, `Permissions-Policy`.
- Plafond de taille de requête (25 Mo), garde anti zip-bomb sur upload .xlsx, garde-fous anti path-traversal.

## ÉTAT D'AVANCEMENT
**Fait (v1 + v2) :**
- v1 : devis PDF → extraction → correspondance → assemblage → remplissage → ZIP. Cockpit UI. Bibliothèque
  de modèles. Déploiement Windows (service + scripts). Tests.
- v2 : **base de connaissance SQLite** (dédup par n° client, enrichissement sans écrasement, journal) ;
  **Tableau de bord** ; **Historique** (recherche + re-téléchargement) ; **Clients** (recherche →
  fiche → dossier **Chantiers** → contenu du chantier : devis / états & documents / historique) ;
  **Statistiques** ; **Étape de révision** (analyser → corriger → générer) ; **Sécurité renforcée**.

**Reste à faire (prochaines briques) :**
1. **Auto-cocher la fonction du bungalow** (vestiaire/réfectoire/bureau/salle de réunion) dans l'Excel.
   → BLOQUÉ tant qu'on n'a pas les **vrais modèles .xlsx + les cellules exactes** (attendus « lundi »).
   Préparer la logique : mapping bloc → fonction → cellule dans `config/cellules.yaml` + écriture dans `remplissage.py`.
2. **Brancher les vrais fichiers** (attendus du client) :
   - déposer les vrais `.xlsx` dans `templates/` (ou via la bibliothèque) ;
   - renseigner les **cellules exactes** dans `config/cellules.yaml` ;
   - compléter `correspondances.csv` (~25 entrées texte→modèle) ;
   - intégrer les **dossiers CSV** fournis (import à concevoir selon leur format).
3. **Intégration CRM Mistral / S@PHIR** : voir `INTEGRATION_MISTRAL.md`. Client en **S@PHIR cloud**,
   pas d'accès API/données pour l'instant. Point de branchement prêt : couche d'enrichissement de `db.py`
   (ajouter `enrichir_depuis_crm()` + `app/connecteurs/mistral.py` + endpoint `/crm/import` quand l'accès arrive).

## Pièges connus
- Le dossier projet contient un espace dans son chemin parent → toujours **quoter** les chemins en shell.
- Pas de hot-reload en prod : après modif Python, **redémarrer** uvicorn.
- `runtime/` (base + sorties) est **gitignoré** : il ne se transfère pas ; recréer la démo avec `scripts/seed_demo.py`.
