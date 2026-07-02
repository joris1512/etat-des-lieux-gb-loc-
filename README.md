# GB Location — Pré-remplissage des états des lieux

> **C'est une application serveur, pas un fichier à ouvrir.** Une fois installée sur le serveur,
> elle tourne en permanence et tous les postes du réseau l'utilisent depuis leur navigateur
> (`http://ip-du-serveur:8000`). Installation Windows clé en main :
> **[`DEPLOIEMENT_WINDOWS.md`](DEPLOIEMENT_WINDOWS.md)**.

Outil interne. À partir d'un **devis PDF**, il :

1. lit le devis (en-tête + lignes d'articles) ;
2. sélectionne le bon **modèle Excel** pour chaque module via une table de correspondance ;
3. applique la **règle d'assemblage** (N bungalows consécutifs d'un même bloc → 1 état assemblé + N individuels) ;
4. **pré-remplit** chaque état des lieux (client, chantier, lieu + code postal, quantités de mobilier) ;
5. produit un **`.xlsx` par état + un ZIP global**, téléchargeables depuis l'interface.

L'interface est un **cockpit** (application web sombre aux couleurs GB) avec barre latérale.

**Pilotage** : tableau de bord (données réelles persistées), écran **Générer**, bibliothèque de **modèles**.

**Connaissance** — chaque devis enrichit une **base SQLite auto-apprenante** (`runtime/gb.db`) :
- la base reconnaît le **client** par son N° client (jamais de doublon) et mémorise ses
  **adresses**, **interlocuteurs**, **chantiers** et **devis** ;
- elle se **complète** à chaque devis sans écraser ce qu'elle sait déjà, et journalise « ce qu'elle apprend » ;
- **Historique** (recherche + re-téléchargement des dossiers passés), **Clients** (fiches enrichies),
  **Statistiques** (activité, top clients, répartition).

> Socle pensé pour de futurs **agents IA** et un **contrôleur d'automatisation** : entités propres,
> couche d'enrichissement isolée, journal d'apprentissage.

> Périmètre v1 strict : il **reconnaît** le bon modèle et **pré-remplit** l'en-tête et les cases mobilier.
> Il ne touche **jamais** aux fonctions (vestiaire/réfectoire/…), aux champs d'état réel, réserves ou signatures,
> et **ignore** toutes les prestations (transport, assemblage, montage, etc.).

---

## Architecture

```
app/
  config.py          Réglages (.env) + chemins (pathlib, cross-platform)
  models.py          Schémas Pydantic (extraction + plan)
  extraction.py      Devis PDF -> JSON via API Anthropic (bloc document base64)
  correspondance.py  Normalisation texte + table texte->modèle + filtre prestations
  assemblage.py      Logique d'assemblage -> liste d'états à produire
  remplissage.py     Écriture openpyxl (en-tête + mobilier), mise en forme préservée
  generation.py      Orchestrateur : PDF -> .xlsx + ZIP + enrichissement de la base
  db.py              Base de connaissance SQLite auto-enrichissante (clients/devis/chantiers…)
  modeles.py         Gestion de la bibliothèque de modèles (lister/téléverser/supprimer)
  securite.py        Authentification optionnelle (mot de passe, HTTP Basic)
  purge.py           Purge automatique des fichiers générés
  main.py            API FastAPI + interface web (génération / modèles / téléchargement)
  templates_html/    Interface web (application monopage)
  static/            Logo et ressources statiques
correspondances.csv  Table texte -> fichier modèle (éditable ; ~25 entrées à terme)
config/cellules.yaml Cellules d'en-tête + mobilier par modèle (à caler sur les vrais .xlsx)
templates/           Modèles Excel (.xlsx) — les vrais fichiers GB
fixtures/            Extraction pré-calculée du devis EIFFAGE (mode démo hors-ligne)
scripts/             Installateur Windows, service, diagnostic, modèles factices
tests/               Tests (correspondance, assemblage, sécurité, durcissement, bout-en-bout)
```

---

## Installation (dev, macOS)

Prérequis : Python 3.12+ (testé en 3.12 → 3.14).

```bash
cd gb-etats-des-lieux
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Clé API (jamais en dur dans le code) :
cp .env.example .env        # puis renseigner ANTHROPIC_API_KEY

# Modèles Excel : déposer les vrais .xlsx dans templates/.
# En attendant, générer des modèles factices pour tester l'outil :
python scripts/make_placeholder_templates.py
```

## Lancement (dev)

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
# ouvrir http://127.0.0.1:8000
```

Le bouton **« Démo (devis EIFFAGE) »** rejoue l'extraction du devis EIFFAGE **sans appeler l'API**
(pratique pour tester le remplissage + ZIP sans clé).

## Lancement sur le serveur Windows (production)

Aucune modification de code (chemins en `pathlib`, dépendances cross-platform).

### 1. Préparer l'environnement

```bat
cd gb-etats-des-lieux
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

copy .env.example .env
notepad .env       REM ANTHROPIC_API_KEY + GB_PASSWORD + GB_HOST/GB_PORT

REM Déposer les vrais modèles dans templates\ (ou, le temps des tests, générer les factices) :
python scripts\make_placeholder_templates.py
```

### 2a. Lancement simple (fenêtre)

```bat
scripts\run_prod.bat        REM écoute 0.0.0.0:8000 par défaut
```

### 2b. Lancement en service (recommandé — redémarrage auto)

Installe l'appli comme service Windows via [NSSM](https://nssm.cc) (redémarre au boot et en cas de crash) :

```bat
REM Invite "Administrateur", nssm.exe dans le PATH :
scripts\install_service_windows.bat
```

Gestion : `nssm status GBEtatsDesLieux` · `nssm stop GBEtatsDesLieux` · `nssm remove GBEtatsDesLieux confirm`.

Depuis un poste du réseau : `http://IP_DU_SERVEUR:8000` (identifiants `GB_USER` / `GB_PASSWORD`).

### Réglages d'hébergement (`.env`)

| Variable | Rôle | Défaut |
|---|---|---|
| `GB_PASSWORD` | Mot de passe d'accès. **Vide = appli ouverte** (dev). Renseigné = login exigé. | *(vide)* |
| `GB_USER` | Identifiant associé au mot de passe. | `gb` |
| `GB_RETENTION_HEURES` | Purge auto des fichiers générés au-delà de N heures (0 = jamais). | `24` |
| `GB_HOST` / `GB_PORT` | Écoute réseau. | `127.0.0.1` / `8000` |
| `GB_MODEL` | Modèle d'extraction Anthropic. | `claude-opus-4-8` |

---

## Tests

```bash
pytest -q
```

Couvre la normalisation/correspondance, la logique d'assemblage, et un test de bout en bout
sur le devis EIFFAGE (17 états attendus : 11 individuels + 4 assemblés + 2 sanitaires).

---

## Bibliothèque de modèles (depuis l'application)

La page web inclut une rubrique **« Bibliothèque de modèles Excel »** :

- liste des modèles **attendus** (présents ✅ / manquants ⚠), avec taille et date de mise à jour ;
- **téléversement** d'un ou plusieurs `.xlsx` — un fichier de même nom **remplace** l'ancien
  (mise à jour d'un modèle sans accès au serveur), prise en compte immédiate ;
- **suppression** d'un modèle ;
- validation stricte (vrai classeur Excel, nom sécurisé, 20 Mo max).

> Le **nom du fichier** doit correspondre au modèle attendu (colonne `modele` de `correspondances.csv`,
> ou `modele_assemble` de `config/cellules.yaml`). Les cellules de chaque modèle restent décrites
> dans `config/cellules.yaml`.

## Personnalisation (lundi, avec les vrais fichiers)

1. **Modèles** : déposer les vrais `.xlsx` via la rubrique « Bibliothèque de modèles » (ou dans `templates/`).
2. **Cellules** : ouvrir `config/cellules.yaml` et indiquer les vraies cellules d'en-tête et de mobilier.
3. **Table de correspondance** : compléter `correspondances.csv` avec les ~25 entrées officielles
   (texte de ligne → fichier modèle). Un article sans entrée est **signalé** dans l'UI, jamais deviné.

---

## Cas limites gérés

- Article sans correspondance → signalé dans l'UI (« Article non reconnu »), sans bloquer le reste.
- Mobilier non rattachable à une case → signalé (« Mobilier non rattaché… »), jamais inventé.
- Modèle Excel manquant → signalé, les autres fichiers sont quand même produits.
- PDF vide / non-PDF → message d'erreur clair.

## Sécurité

- `ANTHROPIC_API_KEY` est lue **uniquement** depuis `.env` (gitignoré). Ne jamais committer `.env`
  ni coller la clé ailleurs. En cas d'exposition, régénérer la clé sur console.anthropic.com.
- **Accès** : définir `GB_PASSWORD` active une protection par mot de passe (HTTP Basic) sur toutes
  les routes — important car la rubrique « Bibliothèque de modèles » permet de modifier/supprimer
  des modèles. Sur réseau interne de confiance, l'appli peut tourner sans, mais c'est déconseillé
  dès qu'elle est joignable au-delà.
- **Écoute locale par défaut** (`GB_HOST=127.0.0.1`) : l'appli n'est joignable que depuis le poste.
  N'ouvrir au LAN (`0.0.0.0`) qu'avec un reverse proxy **HTTPS** devant — en HTTP clair, les
  identifiants Basic et les données transitent en clair sur le réseau.
- **Mot de passe jamais stocké en clair** : utiliser `GB_PASSWORD_HASH` (PBKDF2-SHA256, 200 000
  itérations) généré par `python scripts/hash_password.py`. Anti-force-brute (429 après 8 échecs/IP),
  comparaison à temps constant, journal d'audit sans donnée nominative inutile.

## Confidentialité (RGPD)

Registre simplifié des traitements de l'outil (usage interne GB Location) :

| Question | Réponse |
|---|---|
| **Données traitées** | Raison sociale, n° client, adresses ; noms des interlocuteurs et commerciaux (données personnelles) ; devis et documents générés. |
| **Finalité** | Pré-remplissage des états des lieux et suivi des dossiers clients (intérêt légitime, relation contractuelle). |
| **Où** | **En local uniquement** : base SQLite `runtime/gb.db` + fichiers `runtime/sorties/` sur le poste/serveur GB. Aucun service tiers, hors appel d'extraction. |
| **Sous-traitant** | Le devis PDF est transmis à l'API Anthropic pour extraction (voir leur DPA) ; il n'est pas utilisé pour entraîner des modèles. Minimisation : seul le devis est envoyé, jamais la base clients. |
| **Durée de conservation** | Documents générés : purge automatique (`GB_RETENTION_HEURES`, ~1 an par défaut). Fiches clients : conservées tant que la relation commerciale existe. |
| **Droit d'accès** | La fiche client (UI) et `GET /clients/{id}` restituent l'intégralité des données détenues sur un client — réponse immédiate à une demande d'accès. |
| **Droit à l'effacement** | Fiche client → bouton **« Effacer ce client (RGPD) »** : supprime fiche, interlocuteurs, chantiers, devis, documents générés **et** les entrées de journal (purge ciblée par identifiant). Trace anonyme conservée (id seul). ⚠️ Ne couvre pas d'éventuels snapshots/sauvegardes du serveur de fichiers — à traiter dans la politique de sauvegarde. |
| **Sécurité** | Accès par mot de passe (hash PBKDF2), en-têtes HTTP durcis, anti-force-brute, journal d'audit anonymisé, aucune donnée personnelle dans les logs serveur. |
