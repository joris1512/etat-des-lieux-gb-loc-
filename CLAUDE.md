# GB Location — Pré-remplissage des états des lieux (contexte projet)

> Ce fichier est lu automatiquement par Claude Code. Il sert à **reprendre le travail** sur une
> autre machine sans perdre le contexte. Voir aussi `README.md` (utilisateur), `HANDOFF.md`
> (reprise), `DEPLOIEMENT_WINDOWS.md` (serveur), `INTEGRATION_MISTRAL.md` (étude CRM).

> **🚨 PRIORITÉ N°1 DU REPRENEUR — HÉBERGEMENT CENTRAL (lire en premier).** Le **2026-08-31**, la
> base partagée `gb.db` a été **VIDÉE** (perte de TOUS les clients + comptes) à cause d'un **accès
> SIMULTANÉ de plusieurs postes** au fichier SQLite sur le partage réseau — la fragilité connue de
> SQLite-sur-SMB (voir « Pièges connus » v2.5.1). Restaurée depuis la **copie OneDrive**
> (`%OneDrive%\Sauvegardes GB Etats des lieux\gb-2026-08-28.zip`, 60 clients + comptes CB/CBO/RI).
> **⚠️ TANT QUE L'APPLI TOURNE EN « FICHIER PARTAGÉ » : NE JAMAIS l'ouvrir sur 2 postes EN MÊME
> TEMPS (risque de re-perte) ; NE JAMAIS lancer un serveur de test sur les VRAIES données pendant
> qu'un autre poste peut y accéder ; NE JAMAIS retirer la copie de sauvegarde OneDrive.**
> **➡️ VRAIE SOLUTION = basculer sur l'HÉBERGEMENT WEB** (kit prêt : `deploy/` + `docs/DEPLOIEMENT_VPS.md`,
> ~quelques heures) : une seule base, tout le monde via un lien, plus aucun risque de concurrence.
> C'est aussi ce qui débloque l'espace chauffeurs (accès mobile). **À faire en priorité.**

> **🔁 PASSATION (26/08/2026).** Le développeur d'origine quitte GB Location. Guide de reprise
> **humain** au niveau supérieur : `..\PASSATION - COMMENCER ICI.html`. **Lancement = depuis les
> sources** (plus d'`.exe` : bloqué par l'antivirus) via `Lancer GB - derniere version.vbs`
> (fixe `GB_DONNEES_DIR` sur le dossier partagé). **Données + clé API** vivent dans
> `..\GB Etats des lieux - donnees\` (la clé survit au départ). **⚠️ Le travail des 24–26/08
> (vrais modèles + R1–R10, 179 tests verts, ruff clean) est fonctionnel mais NON COMMITÉ**
> (WIP sur `main` par-dessus `7daf58f`) — le commiter quand la direction a validé. Health-check
> de reprise fait le 26/08 : pytest 179 OK, ruff clean, app démarre.

> **🛠️ Session 2026-08-27 (commits sur `main`, 179 tests verts à chaque étape) :** `e5a4e9b`
> WIP v2.7.2 enfin commité ; `2ed49cf` `requirements.lock` ; `a862a2c` sauvegardes fiabilisées
> (base **+ documents**, 30 j, **copie OneDrive** via `%OneDrive%` ou `GB_SAUVEGARDE_EXTERNE`) ;
> `34024a0` messages d'erreur clairs (`main._erreur_lisible`) ; `4ac65ce` R1 douches (onglet 4D/6D
> seulement si modèle `douches.xlsx`) + IA `temperature=0` / `max_tokens` 16000 / refus si tronqué ;
> `e21a012` **vrais modèles 2WC branchés** (`sanitaire_2wc_2d_2u`=GRAND SANITAIRE MIXTE,
> `sanitaire_2wc_pmr`=BLOC 2WCH, onglet « 2WCH ») + **clim marquée TOUJOURS** (présente→OUI seul,
> sinon→NON seul, jamais les deux). Sauvegarde code hors-ligne = `..\SAUVEGARDE-CODE GB (...).bundle`.
> **Reste** (nécessite Joris) : dépôt git distant (offsite auto), droits d'accès dossier données,
> choix hébergement. **NON fait volontairement** (risque sans validation live) : `est_prestation`
> mots-entiers ; UI clim/assemblage (abandonné, Joris n'en veut pas). Multi-poste : `python-portable\`
> + `Lancer GB (tous postes).vbs` créés mais **pywebview n'affiche pas** en embeddable → raccourci
> resté sur le lanceur venv d'origine (fenêtre OK sur CE PC).

> **🛠️ Session 2026-08-31 (dernier jour du dev d'origine) — HEAD `df5d514` sur `main`, poussé, 193 tests
> verts, ruff clean.** (1) **Incident perte de données** (voir bannière priorité en tête) : base partagée
> vidée par accès 2 postes → **restaurée depuis OneDrive** (60 clients + comptes). (2) **2 règles métier
> polysani** (commit `df5d514`, tests `tests/test_regle_polysani.py` + `tests/test_titre_bloc.py`) :
> **(a)** `app/assemblage.py` `resoudre_modele` → si **>3 WC ET ≥3 urinoirs** = polysani (handi si « HANDI »),
> règle **prioritaire** (corrige le faux match « N URINOIRS » quand la ligne dit « 4 PTS EAU »), **sauf**
> « GRAND SANITAIRE MIXTE » explicite ; choix manuel toujours prioritaire (helpers `_nb_wc`/`_nb_urinoirs`).
> **(b)** `app/remplissage.py` `resumer_contenu_bloc` réécrit la cellule-titre **A6** des polysani
> (« Sanitaire : BLOC 5WC / 3UR / 4 PTS EAU (POLYSANI) ») avec le contenu réel lu au devis ; piloté par la
> clé `titre_contenu:{cellule,gabarit}` de `config/cellules.yaml` (⚠️ `_cfg_modele` = **liste blanche de
> clés** → toute nouvelle clé de config doit y être ajoutée). (3) **✅ Dépôt GitHub distant EN PLACE**
> (corrige le « reste : dépôt distant » du 27/08) : `origin` = `github.com/joris1512/etat-des-lieux-gb-loc-`,
> `main` poussé. (4) **Installeur multi-poste** : `..\INSTALLATION - nouveau poste\_moteur.ps1` (crée un
> venv local par PC + raccourci), testé. (5) **`P:\Joris` rangé** : dossier « Joris » imbriqué (doublons,
> ≈178 Mo) supprimé ; panneau `..\A LIRE EN PREMIER - Ou aller.txt` ajouté. **⚠️ Validation métier = pytest
> sur COPIES uniquement, JAMAIS de serveur sur les vraies données (cf. incident).** **Reste** : PRIORITÉ N°1
> hébergement central (bannière en tête) ; espace chauffeurs ; droits d'accès dossier données.

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
- v2.1 : **auto-cochage de la fonction du bungalow**. Détection `bloc → fonction` config-driven dans
  `app/fonctions.py` + section `fonctions:` de `config/cellules.yaml` ; report sur `EtatDesLieux.fonction`
  (assemblage) ; **remplacement** de la cellule fonction dans `remplissage.py` (clé `fonction:` par modèle).
  Testé (62 tests verts, ruff clean) et **validé sur le vrai modèle bungalow** (cellules réelles E5/E7/A9).
- v3 : **vrais modèles branchés** (bungalows vide/mobilier/assemblé + 15 sanitaires + conteneur ;
  moteur `patch_xlsx` qui préserve logo + perspectives) ; **menu déroulant par module** (choix auto +
  correction manuelle) ; **éditeur de règles** dans l'UI ; **import CSV clients** ; **application de
  bureau .exe** (pywebview + PyInstaller, `build_exe.bat`) ; **audit RGPD** : effacement client complet
  (base + fichiers + journal ciblé par client_id), fixture pseudonymisée, rétention 8760 h alignée sur
  le registre README, écoute 127.0.0.1 par défaut, mot de passe haché (PBKDF2), logs minimisés.
  (77 tests verts.)
- v2.4 : **Espace chauffeurs** — rôle `chauffeur` (allowlist de chemins dans `exiger_auth`, vue unique
  « Mes constats »), **signature insérée DANS le xlsx** (`patch_xlsx.inserer_image`, oneCellAnchor,
  re-signature sans doublon), manifeste PWA, QR d'accès (`qrcode` en dépendance).
- v2.5 : **niveau pro** — **page de connexion** (`/connexion`, sessions cookie HMAC 7 j, secret en base,
  Basic conservé, redirection de `/`) ; **PWA complète** (icônes 192/512, `/sw.js` versionné) ; **dossier
  de preuve de signature** (SHA-256 du xlsx à la signature, fonction du signataire, « lu et approuvé »,
  `db.journaliser`, empreinte dans le PDF) ; **envoi SMTP au client** (`app/courriel.py`, carte Admin
  + test) ; compression photos côté navigateur ; `GB_PROXY_CONFIANCE` (IP réelle derrière proxy) ;
  carte « Accès à distance » (paramètre `adresse_publique` + QR) ; **kit VPS** (`deploy/` +
  `docs/DEPLOIEMENT_VPS.md` : OVH Debian 12, Caddy HTTPS auto, systemd, sauvegardes). (144 tests verts.)
  **Décision produit : cible = hébergement VPS français (option « pro ») ; l'accès LAN du poste bureau
  est abandonné pour les chauffeurs (pare-feu domaine sans droits admin + chauffeurs en 4G).**
- v2.6 : **espace chauffeurs — navigation + documents.** Le chauffeur recherche un client → ouvre le
  chantier (devis, états des lieux avec Constat/Télécharger, documents). Accès **lecture seule** aux
  clients/chantiers via garde méthode-consciente (`securite._chemin_autorise_chauffeur(methode, chemin)`).
  **Documents de chantier** : table `documents_chantier` + `DOCUMENTS_DIR` (`runtime/documents/{id}/`,
  nom stocké `{doc_id}{ext}` = anti-traversal) ; endpoints `POST/GET/DELETE /chantiers/{id}/documents`
  (ajout chauffeur+bureau, suppression admin, 20 Mo, images compressées client) ; bloc « Documents »
  réutilisé bureau + chauffeur (`htmlDocuments`/`brancherDocuments`). (160 tests verts.)
- v2.7 : **constat pro en 2 temps + checklist par partie.** Le constat se fait en **Début de loc**
  (départ → colonne C, signature GAUCHE ≈ A48) et **Fin de loc** (retour → colonne F, signature
  DROITE ≈ E48) sur le même document ; chaque temps est indépendant (signer l'un le fige sans bloquer
  l'autre). Pour chaque **partie** du module (lue et **regroupée** depuis le formulaire via
  `terrain.analyser_parties`, donc adaptée à chaque bloc), le chauffeur choisit **Bon / Sale / Cassé**
  + note → reporté dans la bonne colonne (`_texte_etat`). `patch_xlsx.inserer_image(..., cle=)` permet
  **2 signatures** (`signature_debut.png` / `signature_fin.png`) qui coexistent. **Décision produit :
  la checklist est LUE DU FORMULAIRE (déterministe, zéro invention), PAS générée par IA** — l'IA reste
  pour lire le devis. (163 tests verts, ruff clean.)

**Reste à faire (prochaines briques) :**
1. **Brancher les vrais modèles.** Les `.xls` du client (dans `P:\Joris\etat des lieux`, **originaux à ne
   jamais modifier**) ont été **convertis en `.xlsx`** dans `modeles_reels/` (via Excel COM ; 2 « NOTICE
   UTILISATION » exclues). Migration à finaliser :
   - choisir le **fichier bungalow canonique** + mapper ses onglets (`bungalow`, `BUNGALOWS ASSEMBLES`,
     `bungalow avec mobilier`) ; gérer la **sélection d'onglet** selon le cas (individuel / assemblé / avec mobilier) ;
   - réécrire `correspondances.csv` (vrais noms de fichiers, ~25 entrées texte → modèle) ;
   - renseigner les **cellules réelles** dans `config/cellules.yaml` (en-tête `E5`/`E7`, fonction `A9`/`B9`/`B12` selon onglet) ;
   - intégrer les **dossiers CSV** fournis (import à concevoir selon leur format).
   ⚠️ Pré-remplissage voulu sur ces modèles = **Client + Chantier + fonction** uniquement (pas le n° de bungalow,
   pas de quantités de mobilier ; le nom du modèle indique « avec / sans mobilier »).
2. **Import .xls dans la bibliothèque** (optionnel) : l'app n'accepte que `.xlsx`. Soit conversion en amont
   (faite via Excel COM), soit conversion automatique à l'upload (dépendrait d'Excel sur le serveur, plus fragile).
3. **Intégration CRM Mistral / S@PHIR** : voir `INTEGRATION_MISTRAL.md`. Client en **S@PHIR cloud**,
   pas d'accès API/données pour l'instant. Point de branchement prêt : couche d'enrichissement de `db.py`
   (ajouter `enrichir_depuis_crm()` + `app/connecteurs/mistral.py` + endpoint `/crm/import` quand l'accès arrive).

## Pièges connus
- Le dossier projet contient un espace dans son chemin parent → toujours **quoter** les chemins en shell.
- Pas de hot-reload en prod : après modif Python, **redémarrer** uvicorn.
- `runtime/` (base + sorties) est **gitignoré** : il ne se transfère pas ; recréer la démo avec `scripts/seed_demo.py`.
- **Console Windows (cp1252)** : les scripts CLI qui impriment des caractères non-latin1 (✔, →, …)
  **forcent `sys.stdout`/`stderr` en UTF-8** (bloc `reconfigure` en tête de `seed_demo.py`, `diagnostic.py`,
  `make_placeholder_templates.py`, `hash_password.py`). Garder ce garde si on ajoute un script. Côté app,
  toutes les lectures fichier utilisent `encoding="utf-8"` explicite (ne pas l'oublier).
- **v2.5.1 — DONNÉES PARTAGÉES SUR LE SERVEUR (choix produit assumé, ne pas régresser).** Les données
  (`DONNEES_DIR`) vivent dans un dossier **partagé à côté du programme** (`P:\Joris\GB Etats des lieux -
  donnees`, sibling de APPLICATION FINALE) pour que **tous les postes partagent la même base**. Comme
  SQLite en **WAL** n'est pas fiable sur SMB, `config.DONNEES_RESEAU` bascule automatiquement db.py en
  `journal_mode=DELETE` + `busy_timeout` sur un chemin réseau. Réserve : robuste pour une petite équipe,
  pas pour des écritures rigoureusement simultanées → la version « béton » multi-utilisateur reste le
  **VPS web** (`docs/DEPLOIEMENT_VPS.md`). Migration auto de l'ancien `%LOCALAPPDATA%` au 1er lancement
  (ouvrir d'abord l'appli sur le poste qui détient déjà les données).
