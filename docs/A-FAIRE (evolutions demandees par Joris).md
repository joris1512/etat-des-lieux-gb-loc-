# À FAIRE — évolutions demandées (pour le repreneur)

> Demandées par Joris le 2026-08-31 (son dernier jour). **À implémenter PROPREMENT, AVEC des
> tests unitaires, et SANS lancer de serveur sur les VRAIES données** (voir l'incident de perte de
> données 2026-08-31 dans `CLAUDE.md`).

## ⛔ PRIORITÉ N°1 (toujours à faire) : héberger l'appli en central
Voir `CLAUDE.md` en tête. Le mode « fichier partagé » a causé une perte de données (base vidée par
accès simultané de 2 postes). Basculer sur l'hébergement web règle ça + débloque les chauffeurs.

---

## ✅ FAIT le 2026-08-31 — les 2 règles polysani ci-dessous sont implémentées + testées

### 1. ✅ Détection automatique « polysani » (sanitaires collectifs)

**Règle métier (Joris) :** un module avec **plus de 3 WC ET au moins 3 urinoirs** est **forcément
un polysani** → `polysani_homme_femme.xlsx` (ou `polysani_handi.xlsx` si le devis précise « HANDI »).
Exemple réel qui échouait : `SANI 15M² H/F 5WC 3 URINOIRS 4 PTS EAU` → sort maintenant
`polysani_homme_femme` tout seul.

**Où :** `app/assemblage.py` → helpers `_nb_wc` / `_nb_urinoirs` + règle **prioritaire** au début de
`resoudre_modele` (prioritaire car sinon un motif « N URINOIRS » de `correspondances.csv` matchait à
tort quand la ligne contient p.ex. « 4 PTS EAU »). **Exception** : « GRAND SANITAIRE MIXTE » explicite
n'est jamais transformé. Le choix manuel de l'utilisateur reste prioritaire sur tout.
**Tests :** `tests/test_regle_polysani.py` (7 tests).

### 2. ✅ Reporter le CONTENU du bloc dans le TITRE de l'état des lieux

**Demande (Joris) :** lire ce qu'il y a dans le module (WC, urinoirs, points d'eau, lavabos…) et
l'écrire dans le titre de l'état des lieux généré. Sur les polysani, c'est la **cellule A6**
(« Sanitaire : BLOC 5WC / 3UR / 4 PTS EAU (POLYSANI) ») : elle est réécrite avec le contenu **réel**
lu au devis, au lieu du texte figé du modèle. Si la ligne est illisible (aucun WC/urinoir reconnu),
on **garde** le titre d'origine (pas de réécriture hasardeuse).

**Où :** `app/remplissage.py` → `resumer_contenu_bloc()` (parse la ligne) + écriture pilotée par la clé
`titre_contenu` (`{cellule, gabarit}`) de `config/cellules.yaml`. **Extensible** : pour appliquer la
même chose à un autre modèle, ajouter `titre_contenu: {cellule: ..., gabarit: "... {contenu} ..."}`
sous ce modèle dans `cellules.yaml` (aucun code à toucher).
**Tests :** `tests/test_titre_bloc.py` (7 tests).

---
*Le menu déroulant de révision reste le filet de sécurité (l'utilisateur peut toujours corriger un
modèle à la main, et l'appli mémorise la ligne exacte).*
