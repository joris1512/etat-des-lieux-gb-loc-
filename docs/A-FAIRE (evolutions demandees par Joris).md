# À FAIRE — évolutions demandées (pour le repreneur)

> Demandées par Joris le 2026-08-31 (son dernier jour). **À implémenter PROPREMENT, AVEC des
> tests unitaires, et SANS lancer de serveur sur les VRAIES données** (voir l'incident de perte de
> données 2026-08-31 dans `CLAUDE.md`). En attendant, le **menu déroulant de révision** couvre ces
> cas (l'utilisateur choisit le bon modèle à la main, et l'appli mémorise la ligne exacte).

## ⛔ PRIORITÉ N°1 (avant ces évolutions) : héberger l'appli en central
Voir `CLAUDE.md` en tête. Le mode « fichier partagé » a causé une perte de données (base vidée par
accès simultané de 2 postes). Basculer sur l'hébergement web règle ça + débloque les chauffeurs.

---

## 1. Détection automatique « polysani » (sanitaires collectifs)

**Règle métier (Joris) :**
- Si un module a **plus de 3 WC ET plus de 3 urinoirs** → c'est **forcément un polysani**.
  - par défaut → `polysani_homme_femme.xlsx`
  - si le devis précise **« HANDI »** → `polysani_handi.xlsx`
- Exemple réel qui échouait : ligne `SANI 15M² H/F 5WC 3 URINOIRS 4 PTS EAU` (bloc « COTE SANITAIRE
  PUBLIC ») → doit sortir `polysani_homme_femme` automatiquement.

**Piste d'implémentation :**
- Parser le nombre de WC et d'urinoirs depuis `ArticleDevis.texte_ligne` (regex `(\d+)\s*WC`,
  `(\d+)\s*URINOIR`) — idéalement dans `app/correspondance.py` ou `app/assemblage.py`.
- Appliquer la règle **en FALLBACK** (après les correspondances spécifiques de `correspondances.csv`),
  pour NE PAS écraser un modèle plus précis (ex. « grand sanitaire mixte »).
- Gérer le cas `HANDI` → `polysani_handi`.

**⚠️ À valider avec le métier + sur de vrais devis** : risque de conflit avec d'autres modèles
(grand mixte, etc.). Ajouter des tests unitaires (comme `tests/test_correspondance.py`).

## 2. Reporter le CONTENU du bloc dans le TITRE de l'état des lieux

**Demande (Joris) :** lire ce qu'il y a dans le module (ex. « 5 WC, 3 urinoirs, 4 points d'eau »)
et l'écrire dans le **titre / en-tête** de l'état des lieux généré (pour décrire le contenu).

**Piste d'implémentation :**
- Extraire le contenu depuis `texte_ligne` (WC, urinoirs, douches, points d'eau…).
- L'écrire dans la bonne cellule du modèle via `app/remplissage.py` / `app/patch_xlsx.py`
  (repérer LA cellule exacte avec Joris ou sur le vrai modèle polysani — cf. `config/cellules.yaml`).
- Ajouter un test (générer sur un vrai modèle, relire la cellule).

---
*Le manuel (menu déroulant) reste le filet de sécurité tant que ce n'est pas fait.*
