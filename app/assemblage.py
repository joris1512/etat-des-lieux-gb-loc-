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
from app.correspondance import est_prestation, trouver_modele
from app.fonctions import detecter_fonction
from app.models import (
    ArticleDevis,
    EtatDesLieux,
    ExtractionDevis,
    MobilierItem,
    PlanGeneration,
)


def _modele_assemble() -> str:
    """Nom du modèle Excel utilisé pour les états assemblés (depuis cellules.yaml)."""
    cfg = yaml.safe_load(CONFIG_CELLULES.read_text(encoding="utf-8"))
    return cfg.get("modele_assemble", "bungalow_assemble.xlsx")


def _bungalow_individuel(avec_mobilier: bool) -> str | None:
    """Modèle de bungalow individuel selon la présence de mobilier (config cellules.yaml)."""
    cfg = yaml.safe_load(CONFIG_CELLULES.read_text(encoding="utf-8")) or {}
    b = cfg.get("bungalow_individuel") or {}
    return b.get("mobilier" if avec_mobilier else "vide")


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
    if entree.est_bungalow:  # variante vide / avec mobilier selon le mobilier listé
        modele = _bungalow_individuel(bool(art.mobilier)) or entree.modele
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
    modele_assemble = _modele_assemble()
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
            # 1 état assemblé (porte le mobilier) ...
            plan.etats.append(
                EtatDesLieux(
                    modele=modele_assemble,
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
