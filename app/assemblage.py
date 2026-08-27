"""Application de la logique d'assemblage : devis extrait -> liste d'états des lieux à produire.

Règles :
- N bungalows consécutifs du MÊME bloc AVEC une ligne d'assemblage explicite (`ArticleDevis.assemble`
  = True, posé quand le devis porte « ASSEMBLAGE DES BUNGALOWS » / « ASSEMBLAGE/DESASSEMBLAGE ») =
  un assemblage -> 1 état « assemblé » (qui regroupe les N) + N états individuels.
- N bungalows consécutifs du même bloc SANS ligne d'assemblage = N états INDIVIDUELS distincts
  (deux bungalows qui se suivent ne sont PAS assemblés automatiquement).
- 1 seule ligne BUNGALOW = 1 état individuel classique.
- Un sanitaire / module spécial (est_bungalow=False) = 1 état individuel avec son propre modèle.

Le mobilier commun d'un groupe de bungalows identiques est RÉPARTI À PARTS ÉGALES entre les N
modules (ex. 12 armoires sur 2 bungalows -> 6 + 6). Il va toujours sur les états INDIVIDUELS,
jamais sur l'état assemblé (qui ne sert qu'à l'inspection de l'ensemble). La présence
d'équipement kitchenette dans ce mobilier commun sert à choisir la variante du modèle assemblé.
"""

from __future__ import annotations

import re

import yaml

from app.config import CONFIG_CELLULES
from app.correspondance import est_prestation, normaliser, trouver_modele
from app.fonctions import detecter_fonction
from app.models import (
    ArticleDevis,
    EtatDesLieux,
    ExtractionDevis,
    MobilierItem,
    PlanGeneration,
)


def _cfg() -> dict:
    return yaml.safe_load(CONFIG_CELLULES.read_text(encoding="utf-8")) or {}


def _modele_assemble(avec_kitchenette: bool = False) -> str:
    """Modèle des états assemblés ; variante « kit » si le bloc comporte une kitchenette."""
    cfg = _cfg()
    if avec_kitchenette and cfg.get("modele_assemble_kit"):
        return cfg["modele_assemble_kit"]
    return cfg.get("modele_assemble", "bungalow_assemble.xlsx")


# Équipement « cuisine » : sa présence dans le mobilier signale une kitchenette.
_MOTS_KITCHENETTE = ("KITCHENETTE", "EVIER", "CHAUFFE EAU", "REFRIGERATEUR", "MICRO ONDES", "PLAQUE")


def _a_kitchenette(mobilier: list[MobilierItem], texte: str = "") -> bool:
    corpus = normaliser(" ".join(m.designation for m in mobilier) + " " + texte)
    return any(mot in corpus for mot in _MOTS_KITCHENETTE)


def _kitchenette_seulement(mobilier: list[MobilierItem]) -> bool:
    """True si le mobilier ne contient QUE de l'équipement kitchenette.

    Le modèle assemblé « kit » n'a pas de lignes d'inventaire mobilier : on ne le choisit que
    quand il n'y a rien d'autre à y écrire ; sinon l'assemblé classique reçoit toute la liste.
    """
    if not mobilier:
        return False
    return all(
        any(mot in normaliser(item.designation) for mot in _MOTS_KITCHENETTE)
        for item in mobilier
    )


def _variante_bungalow(art: ArticleDevis) -> str | None:
    """Choisit la variante de bungalow individuel : taille + mots-clés + mobilier + fonction.

    Ordre des règles (la 1re qui matche gagne) — l'utilisateur peut toujours corriger via le
    menu déroulant de la révision :
      8 m² (± coin sanitaire) → 20 m² → petite enfance → coin sanitaire (± kitchenette)
      → réfectoire (fonction réfectoire + mobilier/kitchenette) → avec mobilier → vide.
    """
    variantes = _cfg().get("bungalow_variantes") or {}
    if not variantes:
        return None
    t = normaliser(f"{art.texte_ligne} {art.bloc or ''}")
    kitch = _a_kitchenette(art.mobilier, t)

    def v(cle: str) -> str | None:
        return variantes.get(cle)

    if "8M2" in t or "8 M2" in t:
        return v("8m2_sanitaire" if ("SANIT" in t or "WC" in t) else "8m2_vide") or v("vide")
    if "20M2" in t or "20 M2" in t:
        return v("20m2_vide") or v("vide")
    if "PETITE ENFANCE" in t or "CRECHE" in t:
        return v("petite_enfance") or v("vide")
    if "COIN SANITAIRE" in t:
        return v("coin_sanitaire_kitchenette" if kitch else "coin_sanitaire") or v("vide")
    if detecter_fonction(art.bloc) == "REFECTOIRE" and (art.mobilier or kitch):
        return v("refectoire_kitchenette") or v("mobilier")
    if art.mobilier:
        return v("mobilier") or v("vide")
    return v("vide")


def _est_wc_autonome(modele: str) -> bool:
    """True si le modèle est un WC autonome — regroupé par paquets de 3 par état des lieux (R2)."""
    return "WC AUTONOME" in normaliser(modele or "")


def _nb_douches(texte: str) -> int | None:
    """Nombre de douches lu sur la ligne (« W4D », « 4 DOUCHES ») pour choisir l'onglet 4D/6D (R1)."""
    m = re.search(r"(\d+)\s*D(?:OUCHE)?S?\b", normaliser(texte or ""))
    return int(m.group(1)) if m else None


def _est_bungalow_modele(modele: str, defaut: bool) -> bool:
    """Devine si un modèle choisi est un bungalow (pour la logique d'assemblage)."""
    m = (modele or "").lower()
    if "bungalow" in m:
        return True
    if any(k in m for k in ("sanitaire", "wc", "urinoir", "douche", "polysani", "lave", "container", "roulante")):
        return False
    return defaut


def resoudre_modele(art: ArticleDevis) -> tuple[str, bool] | None:
    """(modèle, est_bungalow) pour un article. Respecte l'override manuel `art.modele` (choix
    utilisateur à la révision) ; sinon déduit via la table + variante bungalow vide/mobilier.
    Renvoie None si le module n'est pas reconnu.
    """
    if art.modele:  # choix manuel de l'utilisateur
        return art.modele, _est_bungalow_modele(art.modele, art.est_bungalow)
    entree = trouver_modele(art.texte_ligne)
    if entree is None:
        return None
    modele = entree.modele
    if entree.est_bungalow:  # déduction de la variante (taille / mobilier / fonction / mots-clés)
        modele = _variante_bungalow(art) or entree.modele
    return modele, entree.est_bungalow


def _lisible(texte: str | None) -> str:
    """Texte lisible et sûr pour un nom de fichier Windows (sans caractères interdits)."""
    if not texte:
        return ""
    t = re.sub(r'[\\/:*?"<>|]+', " ", texte)  # caractères interdits sous Windows
    t = t.replace(" - ", " ")  # réserve « - » au séparateur du nom de fichier
    return re.sub(r"\s+", " ", t).strip()


def _fusionner_mobilier(articles: list[ArticleDevis]) -> list[MobilierItem]:
    """Met en commun le mobilier d'un ensemble de modules (somme par désignation, ordre préservé)."""
    cumul: dict[str, int] = {}
    for art in articles:
        for item in art.mobilier:
            cumul[item.designation] = cumul.get(item.designation, 0) + item.quantite
    return [MobilierItem(designation=d, quantite=q) for d, q in cumul.items()]


def _repartir(mobilier: list[MobilierItem], n: int) -> list[list[MobilierItem]]:
    """Répartit chaque ligne de mobilier à parts ÉGALES entre n modules (règle R10).

    Ex. 12 armoires sur 2 bungalows -> 6 + 6 ; 4 tables sur 2 -> 2 + 2 ; 16 chaises sur 2 -> 8 + 8.
    Un reste éventuel (quantité non divisible par n) est attribué aux PREMIERS modules
    (ex. 13 sur 2 -> 7 + 6). Pour n == 1, le module reçoit tout le mobilier.
    """
    if n <= 0:
        return []
    parts: list[list[MobilierItem]] = [[] for _ in range(n)]
    for item in mobilier:
        base, reste = divmod(item.quantite, n)
        for i in range(n):
            q = base + (1 if i < reste else 0)
            if q > 0:
                parts[i].append(MobilierItem(designation=item.designation, quantite=q))
    return parts


def construire_plan(extraction: ExtractionDevis) -> PlanGeneration:
    """Transforme l'extraction du devis en plan d'états des lieux à produire."""
    plan = PlanGeneration(entete=extraction.entete)
    seq = 0  # compteur global -> préfixe de fichier unique et ordonné

    def nom_fichier(bloc: str | None, type_label: str) -> str:
        """Nom de fichier lisible : « NN - CLIENT - ce que c'est - type.xlsx »."""
        nonlocal seq
        seq += 1
        client = _lisible(extraction.entete.client) or "Client"
        quoi = _lisible(bloc)
        morceaux = [f"{seq:02d}", client] + ([quoi] if quoi else []) + [type_label]
        return " - ".join(morceaux) + ".xlsx"

    # Résolution modèle + nature pour chaque article (override manuel prioritaire, sinon déduction).
    resolus: list[tuple[ArticleDevis, str, bool]] = []  # (article, modele, est_bungalow)
    for art in extraction.articles:
        # Normalise le bloc : "" ou blanc => None (évite de fusionner des modules sans étiquette).
        art.bloc = (art.bloc or "").strip() or None
        res = resoudre_modele(art)
        if res is None:
            if not est_prestation(art.texte_ligne):
                plan.non_reconnus.append(art.texte_ligne)
            continue  # prestation / non reconnu -> pas d'état
        modele, est_bung = res
        # En résolution automatique, on signale une divergence de type devis (LLM) vs table.
        if art.modele is None and est_bung != art.est_bungalow:
            attendu = "bungalow" if est_bung else "non-bungalow"
            lu = "bungalow" if art.est_bungalow else "non-bungalow"
            plan.avertissements.append(
                f"Type incertain pour « {art.texte_ligne} » : devis lu comme {lu}, "
                f"table = {attendu} (la table fait foi)."
            )
        resolus.append((art, modele, est_bung))

    # Regroupement en "runs" de bungalows consécutifs du même bloc.
    run: list[tuple[ArticleDevis, str]] = []  # (article, modele) du bungalow standard
    run_bloc: str | None = None
    wc_run: list[ArticleDevis] = []  # WC autonomes consécutifs, à regrouper par 3 (R2)
    wc_modele: str | None = None

    def cloturer_run() -> None:
        nonlocal run, run_bloc
        if not run:
            return
        articles = [a for a, _ in run]
        bloc = run_bloc
        fonction = detecter_fonction(bloc)
        pooled = _fusionner_mobilier(articles)
        n = len(articles)
        parts = _repartir(pooled, n)  # mobilier commun réparti à parts égales (R10)
        # Modèle commun du groupe : les N bungalows identiques partagent le mobilier commun, donc
        # la MÊME variante — choisie d'après le mobilier COMMUN (et non une seule ligne de devis).
        if n == 1:
            modele_groupe = run[0][1]
        else:
            # Les N bungalows du groupe partagent le mobilier COMMUN -> même variante, choisie
            # d'après ce mobilier commun (PAS le modèle auto-déduit de la 1re ligne, souvent « vide »
            # quand le mobilier est listé sous la 2e ligne : sinon le mobilier réparti ne s'afficherait
            # pas car le modèle « vide » n'a pas de zone mobilier).
            rep = ArticleDevis(
                texte_ligne=articles[0].texte_ligne,
                bloc=articles[0].bloc,
                est_bungalow=True,
                mobilier=pooled,
            )
            modele_groupe = _variante_bungalow(rep) or run[0][1]
        # R4 : on n'assemble QUE si le devis porte une ligne d'assemblage pour ce groupe.
        assembler = n >= 2 and any(a.assemble for a in articles)

        if assembler:
            # 1 état assemblé SANS mobilier (le mobilier commun ne sert qu'au choix kit/classique)…
            plan.etats.append(
                EtatDesLieux(
                    modele=_modele_assemble(avec_kitchenette=_kitchenette_seulement(pooled)),
                    type_etat="assemble",
                    bloc=bloc,
                    fonction=fonction,
                    texte_ligne=articles[0].texte_ligne,
                    nb_modules=n,
                    mobilier=[],
                    nom_fichier=nom_fichier(bloc, "assemblé"),
                )
            )
            # … + N individuels, chacun avec SON modèle résolu et sa part du mobilier commun.
            for i in range(1, n + 1):
                plan.etats.append(
                    EtatDesLieux(
                        modele=modele_groupe,
                        type_etat="individuel",
                        bloc=bloc,
                        fonction=fonction,
                        texte_ligne=run[i - 1][0].texte_ligne,
                        nb_modules=1,
                        index_module=i,
                        mobilier=parts[i - 1],
                        climatisation=run[i - 1][0].climatisation,
                        nom_fichier=nom_fichier(bloc, f"individuel {i}"),
                    )
                )
        elif n == 1:
            # Bloc d'un seul module : 1 état individuel qui porte le mobilier.
            plan.etats.append(
                EtatDesLieux(
                    modele=run[0][1],
                    type_etat="individuel",
                    bloc=bloc,
                    fonction=fonction,
                    texte_ligne=articles[0].texte_ligne,
                    nb_modules=1,
                    mobilier=parts[0],
                    climatisation=articles[0].climatisation,
                    nom_fichier=nom_fichier(bloc, "individuel"),
                )
            )
        else:
            # Plusieurs bungalows identiques SANS ligne d'assemblage (R4) : N états INDIVIDUELS
            # distincts ; le mobilier commun est réparti à parts ÉGALES entre eux (R10).
            for i in range(1, n + 1):
                plan.etats.append(
                    EtatDesLieux(
                        modele=modele_groupe,
                        type_etat="individuel",
                        bloc=bloc,
                        fonction=fonction,
                        texte_ligne=run[i - 1][0].texte_ligne,
                        nb_modules=1,
                        index_module=i,
                        mobilier=parts[i - 1],
                        climatisation=run[i - 1][0].climatisation,
                        nom_fichier=nom_fichier(bloc, f"individuel {i}"),
                    )
                )
        run = []
        run_bloc = None

    def cloturer_wc() -> None:
        """Émet les états des WC autonomes cumulés, regroupés par paquets de 3 (R2).

        Ex. 6 WC autonomes -> 2 états (3 + 3) ; 4 -> 2 états (3 + 1) ; 1 -> 1 état.
        `nb_modules` porte le nombre de WC couverts par l'état (1 à 3), pour le remplissage.
        """
        nonlocal wc_run, wc_modele
        if not wc_run:
            return
        total = sum(max(1, a.quantite) for a in wc_run)
        bloc = wc_run[0].bloc
        texte = wc_run[0].texte_ligne
        reste = total
        while reste > 0:
            n = min(3, reste)
            plan.etats.append(
                EtatDesLieux(
                    modele=wc_modele,
                    type_etat="sanitaire",
                    bloc=bloc,
                    texte_ligne=texte,
                    nb_modules=n,
                    mobilier=[],
                    nom_fichier=nom_fichier(bloc or texte, "sanitaire"),
                )
            )
            reste -= n
        wc_run = []
        wc_modele = None

    for art, modele, est_bung in resolus:
        if est_bung:
            cloturer_wc()  # un bungalow interrompt une série de WC autonomes
            # Un bungalow rejoint le run courant si même bloc (et bloc défini), sinon nouveau run.
            if run and art.bloc is not None and art.bloc == run_bloc:
                run.append((art, modele))
            else:
                cloturer_run()
                run = [(art, modele)]
                run_bloc = art.bloc
        elif _est_wc_autonome(modele):
            # WC autonomes : on CUMULE les lignes consécutives (même modèle) pour regrouper par 3.
            cloturer_run()
            if wc_run and modele == wc_modele:
                wc_run.append(art)
            else:
                cloturer_wc()
                wc_run = [art]
                wc_modele = modele
        else:
            # Autre sanitaire / spécial : ferme les runs en cours, état autonome avec son modèle.
            cloturer_run()
            cloturer_wc()
            plan.etats.append(
                EtatDesLieux(
                    modele=modele,
                    type_etat="sanitaire",
                    bloc=art.bloc,
                    texte_ligne=art.texte_ligne,
                    nb_modules=1,
                    mobilier=_fusionner_mobilier([art]),
                    nom_fichier=nom_fichier(art.bloc or art.texte_ligne, "sanitaire"),
                )
            )

    cloturer_run()
    cloturer_wc()

    # --- Report des options du devis sur les états (élingage global, doses réparties, nb douches) ---
    entete = extraction.entete
    for e in plan.etats:
        if e.type_etat in ("individuel", "assemble"):
            e.elingage_bas = entete.elingage_point_bas  # R8 : OUI si le devis le précise, NON sinon
        if "DOUCHE" in normaliser(e.texte_ligne) or "DOUCHE" in normaliser(e.modele):
            e.nb_douches = _nb_douches(e.texte_ligne)  # R1 : choix onglet 4D/6D
    # R3 : doses supplémentaires réparties à parts égales entre les états WC autonomes (décision Joris).
    wc_etats = [e for e in plan.etats if _est_wc_autonome(e.modele)]
    total_doses = entete.doses_wc_supplementaires or 0
    if wc_etats and total_doses:
        base, reste = divmod(total_doses, len(wc_etats))
        for i, e in enumerate(wc_etats):
            e.doses = base + (1 if i < reste else 0)

    return plan
