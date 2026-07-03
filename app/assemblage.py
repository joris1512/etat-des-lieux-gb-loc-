"""Application de la logique d'assemblage : devis extrait -> liste d'états des lieux à produire.

Règle (la seule vraie logique) :
- N lignes BUNGALOW consécutives appartenant au MÊME bloc fonctionnel = un assemblage de N modules.
  -> on génère 1 état « assemblé » (qui regroupe les N) + N états « bungalow 15m2 » individuels.
- 1 seule ligne BUNGALOW = 1 état individuel classique.
- Un sanitaire / module spécial (est_bungalow=False) = 1 état individuel avec son propre modèle.

Le mobilier d'un bloc est mis en commun et reporté sur l'état ASSEMBLÉ (qui représente l'unité
complète) ; pour un bloc d'un seul module, le mobilier va sur l'état individuel.
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

    def cloturer_run() -> None:
        nonlocal run, run_bloc
        if not run:
            return
        articles = [a for a, _ in run]
        bloc = run_bloc
        fonction = detecter_fonction(bloc)
        mobilier = _fusionner_mobilier(articles)
        n = len(articles)
        if n >= 2:
            # 1 état assemblé (porte le mobilier ; « kit » seulement si 100 % kitchenette) ...
            plan.etats.append(
                EtatDesLieux(
                    modele=_modele_assemble(avec_kitchenette=_kitchenette_seulement(mobilier)),
                    type_etat="assemble",
                    bloc=bloc,
                    fonction=fonction,
                    texte_ligne=articles[0].texte_ligne,
                    nb_modules=n,
                    mobilier=mobilier,
                    nom_fichier=nom_fichier(bloc, "assemblé"),
                )
            )
            # ... + N individuels (en-tête seule), chacun avec SON modèle résolu.
            for i in range(1, n + 1):
                art_i, modele_i = run[i - 1]
                plan.etats.append(
                    EtatDesLieux(
                        modele=modele_i,
                        type_etat="individuel",
                        bloc=bloc,
                        fonction=fonction,
                        texte_ligne=art_i.texte_ligne,
                        nb_modules=1,
                        index_module=i,
                        mobilier=[],
                        nom_fichier=nom_fichier(bloc, f"individuel {i}"),
                    )
                )
        else:
            # Bloc d'un seul module : 1 état individuel qui porte le mobilier.
            plan.etats.append(
                EtatDesLieux(
                    modele=run[0][1],
                    type_etat="individuel",
                    bloc=bloc,
                    fonction=fonction,
                    texte_ligne=articles[0].texte_ligne,
                    nb_modules=1,
                    mobilier=mobilier,
                    nom_fichier=nom_fichier(bloc, "individuel"),
                )
            )
        run = []
        run_bloc = None

    for art, modele, est_bung in resolus:
        if est_bung:
            # Un bungalow rejoint le run courant si même bloc (et bloc défini), sinon nouveau run.
            if run and art.bloc is not None and art.bloc == run_bloc:
                run.append((art, modele))
            else:
                cloturer_run()
                run = [(art, modele)]
                run_bloc = art.bloc
        else:
            # Sanitaire / spécial : ferme le run en cours, état autonome avec son modèle.
            cloturer_run()
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
    return plan
