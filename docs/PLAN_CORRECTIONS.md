# Plan technique des corrections (retours de test)

> Voir le cahier des charges détaillé : `RETOURS_TESTS_BOSS.md` (règles R1–R10, devis D1–D4).
> Principe : avancer par **étapes livrables**, en gardant `pytest` **vert** et l'appli utilisable
> à chaque étape. Devis de test : D1 RAYONIER, D2 PENE, D3 SECOURS CATHOLIQUE, D4 EP SARL.

## Journal d'avancement (session autonome — reprendre ICI)

- 🔧 **Corrections retours réels (2026-08-26)** : modèle **repassé sur Opus** (Haiku inventait la clim) ;
  **lave-mains RETIRÉ** de `templates/` + motif LAVE MAINS retiré (un WC autonome ne doit JAMAIS sortir
  l'état lave-mains) ; **CUVE** branchée (`templates/cuve.xlsx` + motif + cellules A6/A7) ; **mise en eau**
  = nb de WC (`regles_modeles.edits_mise_en_eau`, A37) ; **ville ajoutée au CHANTIER** ; prompt durci
  (clim = false par défaut ; blocs identiques obligatoires pour le regroupement). 179 tests verts.
  ⏳ **En attente du devis EXACT de Joris** qui donne 12+0 (mobilier non réparti), « 2 éviers » et clim
  fausse — irreproductible avec RAYONIER (qui sort 6+6 correct). Sans ce devis, correction à l'aveugle.


- ✅✅ **BASCULE COMPLÈTE FAITE** (2026-08-24). **Toutes les règles R1–R10 opérationnelles de bout en bout.**
  - Vrais modèles branchés dans `templates/` (script `scratchpad/brancher_modeles.py`, factices sauvés
    dans `templates_factices_backup/`). `cellules.yaml` était déjà configuré pour les vrais modèles.
  - Données : `ArticleDevis.climatisation`, `EnteteDevis.elingage_point_bas` + `doses_wc_supplementaires`,
    `EtatDesLieux.{climatisation,elingage_bas,doses,nb_douches}` ; propagés dans `construire_plan`
    (élingage global, doses réparties, nb douches, clim par bungalow). Extraction (prompt) capte tout.
  - Remplissage : `remplir_etat` charge la feuille et applique R5 (effacer les autres fonctions),
    R7 clim, R8 élingage, R3 doses (`regles_modeles.edits_*`), R2 emplacements WC (`wc_emplacements`
    en config), R1 onglet douches 4D/6D + en-tête E4/E6 vs E5/E7.
  - Correspondance : ajout motif « WC AUTONOMES » (pluriel).
  - **Devis RAYONIER (D1) généré EN ENTIER** (10 fichiers, 0 non reconnu) et vérifié : douches sur bon
    onglet, VESTIAIRE gardé/autres effacées, CLIMATISE NON, doses 12 (24÷2), armoires 6 (12÷2), 3 WC.
    ZIP envoyé à Joris pour validation finale.
  - ✅ **Décisions Joris (2026-08-24)** : élingage → **laisser tel quel** (ne rien ajouter là où la ligne
    n'existe pas). Rampes → **NE PAS ajouter de modèles rampe** : la rampe est déjà une ligne dans l'état
    des lieux du bungalow/sanitaire avec lequel elle se loue (elle ne se loue quasi jamais seule).
  - ✅ **D2/D3/D4 générés** : D3 (assemblage) et D4 (clim) parfaits. D2 finalisé (2026-08-24) :
    container 3m reconnu (motif « CONTAINERS ») + **choix d'onglet 3m/6m** dans `remplissage`
    (comme douches) ; **mobilier du 8m² dans « DIVERS » (C46)** via `mobilier_zone` ; **cadenas =
    accessoire** (ajouté à `MOTS_PRESTATION`, pas d'état) ; **`patch_xlsx._activer_onglet`** rend
    l'onglet écrit ACTIF à l'ouverture (corrige les modèles multi-onglets douches/container).
    **Les 4 devis réels : 0 ligne non reconnue.**
  - ⏭️ **Reste** : compléter `correspondances.csv` au fil des futurs devis (nouveau vocabulaire).
    Sinon, les corrections R1–R10 sont **terminées et validées** sur les 4 devis.


- ✅ **R4 + R10 faits** (2026-08-21). `app/models.py` : champ `ArticleDevis.assemble`.
  `app/assemblage.py` : assemblage seulement si `assemble=True` (plus d'assemblage auto de 2 bungalows
  qui se suivent) ; mobilier commun réparti à parts égales via `_repartir()` ; modèle du groupe choisi
  d'après le mobilier COMMUN. Fixture EIFFAGE : `assemble=true` posé sur les 4 groupes assemblés.
  Tests mis à jour (test_assemblage, test_mobilier, test_v2, test_fonctions). **pytest vert (166).**
- ✅ **R2 fait** (2026-08-21). `app/assemblage.py` : `_est_wc_autonome()` + `cloturer_wc()` regroupent
  les WC autonomes consécutifs par paquets de 3 (6 WC → 2 états ; 4 → 3+1 ; 1 → 1). `nb_modules` porte
  le nombre de WC de l'état (pour le remplissage à venir). Tests ajoutés dans test_assemblage.
- ✅ **Extraction : indicateur d'assemblage** (2026-08-21). `app/extraction.py` (prompt SYSTEME) : la
  lecture du devis pose `assemble=true` sur les bungalows d'un groupe portant une ligne
  « ASSEMBLAGE/DESASSEMBLAGE ». (Rend R4 opérationnel sur un vrai devis ; non testable hors-ligne.)
- ✅ **Repères de cellules relevés** (2026-08-21) → `docs/MODELES_CELLULES_REFERENCE.md` : positions
  CLIENT/CHANTIER, fonctions (R5), CLIMATISE (R7), ELINGAGE PT BAS (R8), emplacements WC + doses (R2/R3),
  onglets douches 4D/6D (R1) et container. **Point clé : les positions varient par modèle → repérer les
  libellés par leur TEXTE.**
- ✅ **Primitives de marquage** (2026-08-24) → `app/regles_modeles.py` (+ `tests/test_regles_modeles.py`,
  8 tests verts sur les VRAIS modèles) : `edits_fonction` (R5 : garder le bon, effacer les autres — ne
  touche rien si la fonction retenue est absente), `edits_oui_non` (R7 clim / R8 élingage : efface OUI ou
  NON dans la cellule, vide si le libellé est absent), `onglet_douches` (R1 : 4D→Petit, 6D→Grand).
- ✅ **Décisions Joris** : doses **réparties** entre les états (12+12) ; marquage = **garder le bon,
  effacer les autres** (fonction ET oui/non). Élingage : présent seulement dans BUNG VIDE (`A7`) et
  20M² (`C8`) — absent ailleurs → on saute.
- ✅ **Découverte clé** : `remplissage.py` gère DÉJÀ les vrais modèles (`entete_format` « CLIENT :
  {valeur} », `mobilier_zone` en A46, `feuille`=onglet) et les cellules réelles ≈ celles des factices
  (A46 mobilier identique). `patch_xlsx.ecrire_cellules` ignore les valeurs vides → pour EFFACER, écrire
  un espace " ".
- ✅ **4 démos générées et envoyées à Joris** (dans le scratchpad) sur les VRAIS modèles, couvrant
  R1/R2/R3/R5/R6/R7/R8 : bureau climatisé (EP SARL), WC autonome + doses, douches 4D, vestiaire + élingage.
  **En attente de sa validation du placement/format avant la bascule complète.**
- ⏸️ **PALIER — bascule complète (à faire après validation des démos).** Remplacer le CONTENU des
  `templates/*.xlsx` par les vrais modèles (mêmes noms), recaler `cellules.yaml` (coordonnées + onglets
  douches/container + entete_format par modèle), intégrer R5/R7/R8 dans `remplir_etat` (charger le ws,
  calculer les edits via `regles_modeles`, " " pour effacer), R2 (emplacements WC selon `nb_modules`),
  R3 (doses réparties), R1 (onglet douches selon nb), + 6 modèles RAMPE. Mettre à jour les tests
  dont les valeurs de cellules changent.
- ⏸️ **Note historique (reprise) :** Les étapes restantes (R1, R3, R5, R6, R7, R8 + branchement
  `modeles_reels/` + `cellules.yaml` par modèle + 6 modèles RAMPE) modifient la SORTIE Excel et
  demandent : (a) sa validation visuelle des cellules, (b) ses décisions — doses par état ou total ?
  comment marquer la fonction gardée et les OUI/NON (entourer / gras / retirer les autres) ?
  → **Ne pas basculer les vrais modèles sans lui** (risque de documents faux). Logique + extraction
  sont prêtes et testées pour accueillir ces réglages.
- ⚠️ **À VALIDER avec Joris (ne pas basculer sans lui)** : le branchement des vrais modèles
  (`modeles_reels/`) + les cellules exactes (`cellules.yaml`) pour R1/R3/R5/R6/R7/R8. Repères déjà
  trouvés : WC AUTONOME = 3 emplacements A7/A8/A9, doses en A36 ; DOUCHES = onglets « Petit Sanitaire
  Douche » (4D) / « Grand Sanitaire Douche » (6D).
- ❓ **Questions ouvertes pour Joris** : doses réparties par état ou total sur chaque état ?
  Où va le « oui/non » élingage/clim sur le modèle (cellule) ?

## Où vit chaque problème (diagnostic)

| Règle | Fichier(s) concerné(s) | Nature |
|---|---|---|
| R4 assemblage à tort | `app/assemblage.py` (`cloturer_run`, `n >= 2`) + `app/extraction.py` (ligne ASSEMBLAGE ignorée) | Logique + extraction |
| R10 mobilier à répartir | `app/assemblage.py` (mobilier pris par article, pas réparti) | Logique |
| R2 WC auto ÷3 | `app/assemblage.py` (sanitaires non regroupés) + `remplissage` | Logique + cellules |
| R1 onglet 4D/6D | `app/correspondance.py` + `app/remplissage.py` (choix d'onglet) + `cellules.yaml` | Correspondance + remplissage |
| R3 doses | `app/extraction.py` (doses ignorées) + `remplissage` + `cellules.yaml` | Extraction + remplissage |
| R5 garder la bonne fonction | `app/remplissage.py` (suppression des autres sections) + `cellules.yaml` | Remplissage |
| R6 mobilier 8 m² | `app/remplissage.py` / `cellules.yaml` (mapping mobilier du modèle 8 m²) | Remplissage |
| R7 clim oui/non | `app/extraction.py` (clim ignorée) + `remplissage` + `cellules.yaml` | Extraction + remplissage |
| R8 élingage bas oui/non | `app/extraction.py` (élingage ignoré) + `remplissage` + `cellules.yaml` | Extraction + remplissage |

## Étapes

- **Étape 0 — Socle « vrais modèles ».** Faire pointer l'appli sur `modeles_reels/` (aujourd'hui elle
  lit `templates/` avec des modèles provisoires). Réécrire `correspondances.csv` avec les vrais noms de
  fichiers + les patterns sanitaires réels (`W3WC`→BLOC 3WC, `W4D`→DOUCHES 4D, `W6D`→DOUCHES 6D, `2WC 2D 2U`
  →GRAND SANITAIRE MIXTE, `1WC 1D 1U`→PETIT SANITAIRE MIXTE, `2WC 2UR`→SANITAIRE 2WC_2UR, WC AUTONOME…).

- **Étape 1 — Extraction enrichie.** `models.py` + prompt `extraction.py` : capter par bloc/module
  → fonction, mobilier (à répartir), **clim** (oui/non), **élingage bas** (oui/non), **doses** (nombre),
  **assemblage** (présence de la ligne), type/nombre de sanitaire (nb WC, nb douches).

- **Étape 2 — Plan / assemblage** (`assemblage.py`, testable hors-ligne sur D1–D4) :
  R4 (assembler seulement si ligne ASSEMBLAGE) · R10 (répartir le mobilier ÷ N) · R2 (WC auto par paquets de 3).

- **Étape 3 — Remplissage & cellules** (`remplissage.py`, `patch_xlsx.py`, `config/cellules.yaml`) :
  R1 onglet 4D/6D · R2 retirer les emplacements WC en trop · R3 remplir doses · R5 garder la bonne fonction ·
  R6 mobilier 8 m² · R7 clim oui/non · R8 élingage oui/non. (Nécessite d'ouvrir chaque modèle pour repérer
  les cellules exactes.)

- **Étape 4 — Modèles manquants.** Ajouter les 6 RAMPE/TERRASSE (convertir en .xlsx + correspondances).

- **Validation continue.** Après chaque étape : `pytest -q` vert + `ruff` clean + essai sur D1–D4.

## Notes
- Étape 2 est **testable hors-ligne** (fixtures = extractions des 4 devis) → on la sécurise par des tests
  avant de toucher l'extraction IA.
- Les Étapes 1/3/7/8 (clim, élingage, doses) sont aujourd'hui **jetées à l'extraction** (`extraction.py`
  ignore ces lignes) : il faut d'abord les **capter** avant de pouvoir les remplir.
