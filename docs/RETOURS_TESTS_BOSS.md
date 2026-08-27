# Retours de test (avec la direction) — cahier des charges des corrections

> Établi à partir de 4 devis réels. Statut : ⬜ à faire · 🔄 en cours · ✅ fait.
>
> **Devis de référence :**
> - **D1** RAYONIER A.M TARTAS — GB00007792/L : sanitaires (3WC×2, 4D×2) + vestiaires×2 + réfectoires×2 + 6 WC auto + doses + élingage point bas.
> - **D2** SARL PENE PEINTURE — GB00008195/L : bungalow 8 m² **meublé** + container 3 m + cadenas + 1 WC auto.
> - **D3** SECOURS CATHOLIQUE — GB00008245/L : 2 bungalows **assemblés** (`ASSEMBLAGE DES BUNGALOWS`) = ensemble 30 m² stockage vide. « Pas de climatisation ».
> - **D4** EP SARL — GB00008147/L : bungalow **BUREAU** meublé **+ OPTION CLIMATISATION** + 1 WC auto + 1 dose supp. Élingage point **haut** seulement.

## Structure d'un devis (à bien extraire)

Modules regroupés sous un **titre de fonction** (majuscules, sans prix), puis lignes bungalow, puis
mobilier (quantités **totales** à répartir), puis parfois options (clim…). Le titre peut être **avant**
(D1 : `VESTIAIRES…`, `REFECTOIRE…`) ou **après** le bloc (D3 : `ENSEMBLE MODULAIRE 30M²… STOCKAGE`,
D4 : `BUREAU`).

---

## A. Choix du bon modèle & quantités

- **R1 — ⬜ Douches : bon onglet.** `Petit Sanitaire Douche` = **4 D**, `Grand Sanitaire Douche` = **6 D**.
  D1 : `PETIT SANITAIRE W4D (4 DOUCHES)` ×2 ⇒ 2 états 4D. `PETIT SANITAIRE W3WC (3wc)` ×2 ⇒ 2 états BLOC 3WC.

- **R2 — ⬜ WC autonomes : 3 par état, et n'afficher que le nombre réel.**
  1 état « WC autonome » = **3 WC max**. Si moins de 3, **enlever les emplacements en trop** (ne laisser
  que le nombre réel).
  D1 : 6 WC → **2 états** (3+3). D2/D4 : 1 WC → **1 état avec 1 seul emplacement** (retirer les 2 autres).

- **R3 — ⬜ WC autonomes : remplir le nombre de doses (champ déjà présent).**
  D1 : `24 DOSES SUPP.` ⇒ 24. D4 : `1 DOSES SUPP.` ⇒ 1. D2 : aucune dose supp.

## B. Bungalows — assemblage & fonction

- **R4 — ⬜ Assembler UNIQUEMENT si ligne d'ASSEMBLAGE présente.**
  Déclencheur = une ligne **`ASSEMBLAGE…`** (`ASSEMBLAGE DES BUNGALOWS` ou `ASSEMBLAGE/DESASSEMBLAGE`).
  D3 : présente ⇒ les 2 bungalows = **assemblés**. D1 : absente ⇒ vestiaires/réfectoires = **individuels**
  (bug actuel : assemblés à tort).

- **R5 — ⬜ Ne garder que la bonne fonction** sur l'état des lieux (supprimer vestiaire/réfectoire/bureau…
  en trop, garder celle du titre).

## C. Mobilier & options

- **R6 — ⬜ Bungalow 8 m² : un seul modèle, vide ou meublé.** On remplit le mobilier s'il y en a.
  D2 : `BUNGALOW 8M2` + 1 TABLE + 4 CHAISE ⇒ le mobilier doit apparaître.

- **R7 — ⬜ Climatiseur : oui/non selon le devis.** Repérée par `OPTION CLIMATISATION` / `ACCESSOIRE
  CLIMATISATION`, ligne **juste sous le bungalow** (« quasiment toujours écrit avec l'option »).
  D4 : présente ⇒ **oui**. D3 : « Pas de climatisation » ⇒ **non**.

- **R8 — ⬜ Élingage point BAS : oui/non.** Distinguer **point bas** (à reporter) du **point haut** (ignorer).
  D1 : `ELINGAGE POINT BAS` ⇒ **oui**. D4 : `Elingage… point haut` seulement ⇒ **non**. D2 : absent ⇒ **non**.

- **R10 — ⬜ Répartition ÉGALITAIRE du mobilier entre bungalows identiques d'un même groupe.**
  D1 vestiaires : `12 ARMOIRE` / 2 ⇒ **6 + 6**. D1 réfectoires : `16 CHAISE` / 2 ⇒ **8 + 8**,
  `4 TABLE` / 2 ⇒ **2 + 2**. Gérer aussi les 2 bungalows identiques **sans saut de ligne**.
  (D4 : 1 seul bungalow ⇒ pas de partage.)

## D. Abandonné

- **R9 — ✅ Lave-mains : abandonné.**
