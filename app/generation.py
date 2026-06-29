"""Orchestrateur : devis PDF -> états des lieux .xlsx + ZIP, avec rapport d'anomalies."""

from __future__ import annotations

import re
import uuid
import zipfile
from collections import Counter
from pathlib import Path

from app import db
from app.assemblage import construire_plan
from app.config import SORTIES_DIR, TEMPLATES_DIR
from app.extraction import charger_fixture, extraire_depuis_pdf
from app.models import ExtractionDevis, RapportGeneration
from app.purge import purger_anciennes_sorties
from app.remplissage import remplir_etat


def analyser(
    pdf_bytes: bytes | None,
    *,
    utiliser_fixture: bool = False,
    fixture_nom: str = "eiffage_extraction.json",
) -> ExtractionDevis:
    """Lit le devis (API ou fixture) et renvoie l'extraction, SANS rien générer."""
    if utiliser_fixture:
        return charger_fixture(fixture_nom)
    if not pdf_bytes:
        raise ValueError("Aucun PDF fourni.")
    return extraire_depuis_pdf(pdf_bytes)


def generer(
    pdf_bytes: bytes | None,
    *,
    utiliser_fixture: bool = False,
    fixture_nom: str = "eiffage_extraction.json",
) -> tuple[RapportGeneration, Path]:
    """Lit le devis puis génère tous les états des lieux (chemin direct, sans révision)."""
    extraction = analyser(pdf_bytes, utiliser_fixture=utiliser_fixture, fixture_nom=fixture_nom)
    return generer_depuis_extraction(extraction)


def generer_depuis_extraction(extraction: ExtractionDevis) -> tuple[RapportGeneration, Path]:
    """Génère les états des lieux à partir d'une extraction (éventuellement révisée par l'utilisateur)."""
    # 0) Purge des anciennes sorties (évite l'accumulation au fil des générations).
    purger_anciennes_sorties()

    # 2) Plan d'états des lieux (logique d'assemblage).
    plan = construire_plan(extraction)

    rapport = RapportGeneration(
        numero_offre=extraction.entete.numero_offre,
        non_reconnus=list(plan.non_reconnus),
    )
    for ligne in plan.non_reconnus:
        rapport.avertissements.append(f"Article non reconnu (ignoré) : {ligne}")
    rapport.avertissements.extend(plan.avertissements)

    # 3) Remplissage des modèles.
    job_id = uuid.uuid4().hex[:12]
    job_dir = SORTIES_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    for etat in plan.etats:
        modele_path = TEMPLATES_DIR / etat.modele
        if not modele_path.exists():
            rapport.avertissements.append(
                f"Modèle manquant « {etat.modele} » — fichier non généré : {etat.nom_fichier}"
            )
            continue
        try:
            non_mappes = remplir_etat(modele_path, job_dir / etat.nom_fichier, plan.entete, etat)
        except Exception as exc:  # remontée propre, on continue les autres
            rapport.avertissements.append(f"Échec du remplissage de {etat.nom_fichier} : {exc}")
            continue
        rapport.fichiers.append(etat.nom_fichier)
        for d in non_mappes:
            rapport.avertissements.append(f"Mobilier non rattaché à une case sur {etat.nom_fichier} : {d}")

    # 4) ZIP global. Le n° d'offre vient du PDF : on le réduit à un nom de fichier sûr
    #    (neutralise / et \ pour empêcher toute écriture hors du dossier de sortie).
    if rapport.fichiers:
        base_offre = re.sub(r"[^A-Za-z0-9]+", "-", rapport.numero_offre or "devis").strip("-") or "devis"
        zip_nom = f"etats_des_lieux_{base_offre}.zip"
        zip_path = job_dir / zip_nom
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for nom in rapport.fichiers:
                zf.write(job_dir / nom, arcname=nom)
        rapport.zip_nom = zip_nom

    # 5) Enrichissement de la base de connaissance + enregistrement (non bloquant).
    try:
        produits = set(rapport.fichiers)
        fichiers_meta = [
            {"nom": e.nom_fichier, "type": e.type_etat, "bloc": e.bloc}
            for e in plan.etats
            if e.nom_fichier in produits
        ]
        prod_types = Counter(f["type"] for f in fichiers_meta)
        db.enrichir_et_enregistrer(
            entete=extraction.entete,
            counts={
                "etats": len(fichiers_meta),
                "assembles": prod_types.get("assemble", 0),
                "individuels": prod_types.get("individuel", 0),
                "sanitaires": prod_types.get("sanitaire", 0),
                "non_reconnus": len(plan.non_reconnus),
            },
            fichiers=fichiers_meta,
            job_id=job_dir.name,
            zip_nom=rapport.zip_nom,
        )
    except Exception as exc:  # noqa: BLE001
        rapport.avertissements.append(f"Base de connaissance non enrichie : {exc}")

    return rapport, job_dir
