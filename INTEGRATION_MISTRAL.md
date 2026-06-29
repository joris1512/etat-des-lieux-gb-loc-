# Intégration Mistral / S@PHIR (étude — à exécuter quand l'accès sera disponible)

> Statut : **étude validée, build en attente**. Déploiement client confirmé : **S@PHIR cloud (web)**
> + extension Chrome **Saphir**. Aucune donnée/API disponible pour l'instant → on documente, on
> branchera le connecteur quand l'accès sera obtenu.

## Contexte
- **Mistral (Aptean)** : ERP/CRM français spécialisé **concessionnaires & loueurs** (mistral.fr).
- **S@PHIR** : nouvel ERP **cloud** de Mistral (la cible ici).
- **MobiVip** : CRM mobile Mistral.
- L'app GB doit récupérer **clients, n° clients, n° devis, adresses, interlocuteurs, chantiers**
  depuis S@PHIR et les **rattacher automatiquement** aux bons clients/chantiers.

## L'architecture est déjà prête à recevoir l'intégration
La couche d'enrichissement existante est **le point de branchement** d'un futur connecteur :
- `app/db.py` → entités **clients / interlocuteurs / chantiers / devis / generations** ;
- reconnaissance/dédup par **n° client** (jamais de doublon), enrichissement **sans écrasement** ;
- journal « ce que la base a appris ».

➡️ Un connecteur Mistral n'a qu'à **mapper** un enregistrement S@PHIR vers un upsert client/chantier/devis.
**Aucune refonte nécessaire.** Prévoir une fonction `enrichir_depuis_crm(...)` (variante de
`enrichir_et_enregistrer` sans génération de fichiers) comme point d'entrée du connecteur.

## Approche recommandée (cible : S@PHIR cloud)
1. **API / web-services S@PHIR (préféré)** — connecteur serveur qui interroge l'API Aptean,
   mappe → `enrichir_depuis_crm`, planifié (toutes les X min) ou sur webhook.
   *Le plus pérenne ; idéal pour les futurs agents IA / contrôleur d'automatisation.*
2. **Pont via l'extension Saphir (repli sans API)** — capter les données affichées dans S@PHIR
   et les POSTer à un endpoint `/crm/import` de l'app. *Sans API, mais plus fragile.*
3. **Flux actuel (déjà opérationnel)** — déposer les **PDF de devis** Mistral dans l'app, qui
   enrichit déjà la base automatiquement. *Zéro intégration ; fonctionne aujourd'hui.*

## À obtenir d'Aptean / de l'admin S@PHIR avant de coder
- [ ] S@PHIR expose-t-il une **API / web-services** ? (documentation, endpoints, format JSON/XML)
- [ ] **Authentification** : clé API / OAuth / jeton ? portée (lecture clients/devis) ?
- [ ] Modèle de données : champs **n° client, n° devis, adresses, interlocuteur, commercial, chantier**.
- [ ] **Webhooks** disponibles (nouveau devis / nouveau client) ou polling uniquement ?
- [ ] Ce que fait exactement l'**extension Saphir** (peut-elle exposer/exporter des données ?).
- [ ] À défaut d'API : possibilité d'**export planifié** (CSV/XML) clients + devis.

## Prochaines étapes côté app (quand l'accès est là)
1. Ajouter `enrichir_depuis_crm()` dans `app/db.py` (upsert sans génération).
2. Créer `app/connecteurs/mistral.py` (client API + mapping S@PHIR → entités GB).
3. Endpoint `/crm/import` (+ planification) et/ou réception webhook.
4. Tests d'intégration + rapprochement par n° client (anti-doublon déjà en place).
