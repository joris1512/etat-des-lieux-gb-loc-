# Repères de cellules des VRAIS modèles (`modeles_reels/`)

> Relevé par inspection openpyxl (2026-08-21) pour préparer le branchement des vrais modèles et
> le remplissage (R1/R2/R3/R5/R6/R7/R8). **À FAIRE VALIDER par Joris** (ouvrir chaque fichier).
> ⚠️ Les positions varient d'un modèle à l'autre → le remplissage doit repérer les libellés par
> leur TEXTE (ex. chercher « BUREAU » dans la ligne), pas par une case fixe universelle.

## Bungalows (VIDE / 8M² / MOBILIER 15m²) — même famille, positions proches
- En-tête : `E5` = « CLIENT : », `E6` = « CHANTIER : » (valeur à écrire à côté / cellule fusionnée).
- `A5` = « Bungalow n° : … », `D5` = taille (« 15M² » / « 8M² »).
- **R5 — fonctions sur la LIGNE 8** (4 cases, ordre VARIABLE selon le modèle) :
  - VIDE : `B8`=SALLE DE REUNION, `D8`=VESTIAIRE, `E8`=BUREAU, `G8`=REFECTOIRE
  - 8M² : `B8`=REFECTOIRE, `D8`=BUREAU, `E8`=SALLE DE REUNION, `G8`=VESTIAIRE
  - MOBILIER : `B8`=SALLE DE REUNION, `D8`=VESTIAIRE, `E8`=BUREAU, `G8`=REFECTOIRE
  → garder/marquer la bonne fonction, retirer les 3 autres. **Repérer par texte.**
- **R7 — clim** : `A9` = « CLIMATISE : OUI NON » ; `A10` = « CLIM N° : … AVEC CR ».
- **R8 — élingage** : `A7` = « ELINGAGE PT BAS : OUI NON » **dans le modèle VIDE**. ⚠️ Absent en 8M²
  et MOBILIER (A7 = « N° vitrage : ») → à vérifier où (ou si) il figure dans ces modèles.
- Mobilier (R6) : zone mobilier plus bas (cf. cellules.yaml actuel pour les placeholders ; à recaler
  sur les vrais — le 8M² utilise le MÊME modèle rempli ou non).

## Bungalow ASSEMBLES
- `E6` = CLIENT, `E7` = CHANTIER. Plusieurs « Bungalow n° » en `A6..A10` (les N modules).
- `E9` = « CF ETAT DES LIEUX DETAILLE PAR MODULE CI-JOINT ».
- Fonctions sur la **LIGNE 12** : `B12`=VESTIAIRE, `C12`=REFECTOIRE, `E12`=BUREAU, `G12`=SALLE DE REUNION.

## WC AUTONOME (onglet « WC CHIMIQUE »)
- `E5` = CLIENT, `E7` = CHANTIER.
- **R2 — 3 emplacements WC** : `A7`, `A8`, `A9` (« V : … »). Si < 3 WC, retirer les emplacements en trop.
- **R3 — doses** : `A36` = « DOSES SUPPLEMENTAIRES » ; `A37` = « Mise en eau + 1 dose ». (Nombre à écrire
  à côté / à confirmer la cellule exacte.)
- `A39` = « RAMPE ».

## DOUCHES (fichier `ETAT DES LIEUX DOUCHES.xlsx`, plusieurs onglets)
- **R1 — choix d'onglet selon le nombre de douches** :
  - `Petit Sanitaire Douche` → **4 douches** (`A5` = « Sanitaire : BLOC .. DOUCHES »).
  - `Grand Sanitaire Douche` → **6 douches** (`A6` = « Sanitaire : BLOC 6 DOUCHES »).
  - (autres onglets : `INFOS`, `Grand Sanit 4 Douches A01189`.)
- En-tête : CLIENT `E4`/`E5`, CHANTIER `E6`/`E7` (positions DIFFÉRENTES entre les 2 onglets !).

## BLOC 3WC (onglet « WC »)
- `A6` = « Sanitaire : BLOC 3WC », CLIENT `E5`, CHANTIER `E7`.

## CONTAINER (4 onglets selon la taille)
- Onglets : `CONTAINER 6m (perspectives)`, `CONTAINER 6m`, `CONTAINER 3m 10pieds`, `CONTAINER 3m 8pieds`.
  → choisir l'onglet selon la taille écrite sur le devis (D2 : « CONTAINERS 3M » → onglet 3m).
- `A6` = « Container : C°… », CLIENT `E5`, CHANTIER `E7`, `A8` = « TAILLE : ».

## Conséquences pour le branchement (Étape 0/3)
1. `cellules.yaml` doit être **par modèle** (en-tête à des positions différentes).
2. Le **choix d'onglet** est nécessaire pour DOUCHES (4D/6D), CONTAINER (taille), et déjà géré ailleurs.
3. R5/R7/R8 : repérer les libellés **par leur texte** dans la ligne, puis marquer OUI/NON ou garder la
   bonne fonction — définir AVEC Joris **comment** marquer (entourer ? mettre en gras ? retirer les autres ?).
