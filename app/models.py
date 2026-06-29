"""Schémas Pydantic — sortie d'extraction du devis et plan d'états des lieux à produire."""

from __future__ import annotations

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Extraction du devis (ce que renvoie l'API Anthropic, validé par Pydantic)
# --------------------------------------------------------------------------- #
class MobilierItem(BaseModel):
    """Une ligne de mobilier/équipement rattachée à un module."""

    designation: str = Field(description="Libellé exact de la ligne de mobilier du devis.")
    quantite: int = Field(description="Quantité lue sur la ligne du devis.")


class ArticleDevis(BaseModel):
    """Un article 'module' du devis (bungalow ou sanitaire), dans l'ordre du devis."""

    texte_ligne: str = Field(
        description="Texte EXACT de la ligne d'article, tel quel (ex. 'BUNGALOW 15m2 BATISO')."
    )
    bloc: str | None = Field(
        default=None,
        description=(
            "Libellé de l'unité fonctionnelle à laquelle appartient le module "
            "(ex. 'REFECTOIRE', '2 BUREAUX INDEPENDANTS', 'SALLE DE REUNION'). "
            "Sert UNIQUEMENT à regrouper les modules consécutifs d'un même assemblage."
        ),
    )
    est_bungalow: bool = Field(
        description="True si c'est un bungalow 15m2 standard assemblable ; False pour un sanitaire/spécial."
    )
    quantite: int = Field(default=1, description="Quantité de la ligne (en général 1).")
    mobilier: list[MobilierItem] = Field(
        default_factory=list,
        description="Mobilier/équipement gratuit listé sous ce module (tables, chaises, armoires…).",
    )


class EnteteDevis(BaseModel):
    """En-tête du devis : sert au remplissage Excel ET à l'enrichissement de la base.

    Les champs `adresse` / `code_postal` / `ville` désignent le LIEU D'UTILISATION (chantier),
    repris dans l'en-tête de l'état des lieux. Les champs `*_client` désignent l'adresse de
    facturation / siège du client. La base les distingue.
    """

    # --- Client (entité connue de la base) ---
    client: str = Field(description="Raison sociale du client.")
    numero_client: str | None = Field(default=None, description="N° Client GB (identifiant stable).")
    interlocuteur: str | None = Field(
        default=None, description="Personne à l'attention de qui le devis est adressé."
    )
    commercial: str | None = Field(default=None, description="Commercial GB en charge du devis.")
    adresse_client: str | None = Field(default=None, description="Adresse de facturation / siège du client (voie).")
    code_postal_client: str | None = Field(default=None, description="Code postal du client.")
    ville_client: str | None = Field(default=None, description="Ville du client.")

    # --- Devis ---
    numero_offre: str | None = Field(default=None, description="Numéro d'offre / de devis.")
    date_devis: str | None = Field(default=None, description="Date du devis (texte tel quel).")

    # --- Chantier / lieu d'utilisation (en-tête de l'état des lieux) ---
    titre_chantier: str = Field(description="Intitulé du chantier / lieu d'utilisation.")
    adresse: str = Field(description="Adresse du lieu d'utilisation (voie).")
    code_postal: str = Field(description="Code postal du lieu d'utilisation.")
    ville: str | None = Field(default=None, description="Ville du lieu d'utilisation.")


class ExtractionDevis(BaseModel):
    """Résultat structuré complet de la lecture du devis."""

    entete: EnteteDevis
    articles: list[ArticleDevis] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Plan de production (après application de la logique d'assemblage)
# --------------------------------------------------------------------------- #
class EtatDesLieux(BaseModel):
    """Un état des lieux à générer (1 fichier .xlsx)."""

    modele: str = Field(description="Nom du fichier modèle .xlsx à utiliser.")
    type_etat: str = Field(description="'individuel' | 'assemble' | 'sanitaire'.")
    bloc: str | None = Field(default=None, description="Unité fonctionnelle d'origine.")
    fonction: str | None = Field(
        default=None,
        description=(
            "Fonction du bungalow déduite du bloc (BUREAU / SALLE DE REUNION / VESTIAIRE / "
            "REFECTOIRE), reportée sur la ligne « fonction » du modèle. None si indéterminée."
        ),
    )
    texte_ligne: str = Field(description="Texte de la ligne de devis à l'origine de l'état.")
    nb_modules: int = Field(default=1, description="Nombre de modules regroupés (N pour un assemblé).")
    index_module: int | None = Field(
        default=None, description="Rang du module (1..N) pour un individuel issu d'un assemblage."
    )
    mobilier: list[MobilierItem] = Field(default_factory=list)
    nom_fichier: str = Field(description="Nom du fichier .xlsx produit.")


class PlanGeneration(BaseModel):
    """Plan complet : en-tête commune + états à produire + anomalies signalées."""

    entete: EnteteDevis
    etats: list[EtatDesLieux] = Field(default_factory=list)
    non_reconnus: list[str] = Field(
        default_factory=list, description="Lignes d'article sans correspondance dans la table."
    )
    avertissements: list[str] = Field(
        default_factory=list, description="Anomalies non bloquantes détectées pendant la planification."
    )


class RapportGeneration(BaseModel):
    """Résultat final renvoyé à l'UI."""

    numero_offre: str | None = None
    fichiers: list[str] = Field(default_factory=list)
    zip_nom: str | None = None
    non_reconnus: list[str] = Field(default_factory=list)
    avertissements: list[str] = Field(default_factory=list)
