"""Extraction du devis PDF -> JSON structuré, via l'API Anthropic (bloc document base64).

Le modèle ne fait QUE de l'extraction (lecture + regroupement par bloc). Toute la logique
d'assemblage est appliquée ensuite côté Python (voir app/assemblage.py).
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

from pydantic import ValidationError

from app.config import FIXTURES_DIR, get_reglages
from app.models import ExtractionDevis

NOM_OUTIL = "enregistrer_devis"

SYSTEME = """\
Tu es un assistant qui lit des devis de location de modulaires (société GB Location) et en \
extrait une structure JSON, SANS rien interpréter au-delà de ce qui est écrit.

Tu dois remplir l'outil `enregistrer_devis` avec :

1) entete — distingue bien le CLIENT (destinataire/facturation) du CHANTIER (lieu d'utilisation) :
   • client : raison sociale du client (ex. « EIFFAGE TRX MARITIMES FLUVIAUX »).
   • numero_client : le « N° Client » figurant dans le cartouche (ex. « 007433 »).
   • interlocuteur : la personne « À l'attention de … » (ex. « Mme CAMILLE EXEMPLE »).
   • commercial : le commercial GB (ligne « Commercial : … », ex. « DOMINIQUE DEMO »).
   • adresse_client, code_postal_client, ville_client : l'adresse du CLIENT (bloc destinataire,
     ex. « 3 A 7 PLACE DE L'EUROPE » / « 78140 » / « VELIZY VILLACOUBLAY »).
   • numero_offre : le « N° Offre » (ex. « GB00007589/L »).
   • date_devis : la date du devis (ex. « 03/12/2025 »).
   • titre_chantier : le libellé du « Lieu d'Utilisation » (ex. « CHANTIER ETMF / BESSAC »).
   • adresse, code_postal, ville : l'adresse du LIEU D'UTILISATION / chantier
     (ex. « 1 plage des Casernes » / « 40510 » / « SEIGNOSSE »).
   • elingage_point_bas : true s'il y a une ou des lignes « ELINGAGE POINT BAS » (aller/retour, en
     général près des lignes de transport). Le « point HAUT » ne compte PAS.
   • doses_wc_supplementaires : le NOMBRE (quantité) de la ligne « DOSES SUPP. POUR WC AUTONOMES »
     (0 si absente ; ne pas compter la « mise en eau + 1 dose »).
   • branchement : true s'il y a une ligne « BRANCHEMENT / DÉBRANCHEMENT DES ÉVACS » (raccordement
     à la cuve). Sinon false.
   Laisse vide tout champ absent ; n'invente jamais une valeur.

2) articles : la liste, DANS L'ORDRE DU DEVIS, de TOUS les modules loués — bungalows, sanitaires, \
WC, douches, urinoirs, POLYSANI / GRANDS SANITAIRES, CONTENEURS/CONTAINERS, CUVES (de rétention), \
lave-mains, etc. N'oublie PAS les cuves ni les containers : ce sont des modules à part entière.
   Pour chaque module :
   - texte_ligne : le texte EXACT de la ligne d'article (ex. « BUNGALOW 15m2 BATISO »). \
CAS PARTICULIER « GRANDS SANITAIRES WC » / Polysani : si la description précise « Handi », « PMR » \
ou « Polysani Handi », AJOUTE « HANDI » au texte_ligne (ex. « GRANDS SANITAIRES WC HANDI ») pour le \
distinguer du Polysani standard « Hommes/Femmes ».
   - bloc : le libellé de l'unité fonctionnelle à laquelle ce module appartient (les lignes \
en ** ou *** : VESTIAIRE, REFECTOIRE, 2 BUREAUX INDEPENDANTS, 1 BUREAU INDEPENDANT, 2 BUREAUX, \
SALLE DE REUNION, GARDIEN, SANITAIRES, H/F WC…). Ce libellé apparaît en général juste sous le \
groupe de modules qu'il décrit. Les modules consécutifs d'une même unité doivent porter le MÊME \
libellé de bloc — c'est INDISPENSABLE : deux bungalows identiques qui se suivent sous le même titre \
DOIVENT avoir EXACTEMENT le même libellé de bloc (sinon leur mobilier commun ne sera pas réparti).
   - est_bungalow : true pour un bungalow 15m2 standard assemblable ; false pour tout autre module \
(sanitaire, WC, douches, urinoirs, PMR, polysani, CUVE, CONTAINER…).
   - quantite : la quantité de la ligne (en général 1).
   - assemble : true UNIQUEMENT si le devis comporte une ligne « ASSEMBLAGE DES BUNGALOWS » / \
« ASSEMBLAGE/DESASSEMBLAGE » concernant ce groupe de bungalows (ils sont alors physiquement raccordés \
en un seul ensemble). Sinon false. Deux bungalows identiques qui se suivent ne sont PAS « assemble » \
sans cette ligne d'assemblage explicite.
   - climatisation : PAR DÉFAUT false. Ne mets true QUE si une ligne EXPLICITE « OPTION \
CLIMATISATION » ou « ACCESSOIRE CLIMATISATION » figure pour CE bungalow. En cas de doute : false. \
N'invente JAMAIS une climatisation.
   - mobilier : le mobilier/équipement listé SOUS ce module (tables, chaises, bancs, armoires, \
fauteuils, caissons, réfrigérateur, micro-ondes, évier…), avec sa désignation exacte et sa \
quantité. Quand le mobilier d'un bloc est listé sous le dernier module du bloc, rattache-le à \
ce module.

À IGNORER TOTALEMENT (ne crée AUCUN article pour ces lignes) :
- toutes les prestations : transport, manutention, élingage, superposition/désuperposition, \
configuration, assemblage/désassemblage, montage/démontage, prestation extérieure, escalier, \
ring, carburant, indexation, PIRL, branchement eau/élec ;
- l'option climatisation globale (CLIMATISEUR, MONTAGE/DEMONTAGE CLIM) ;
- toute ligne marquée « annulé » ou « OFFERT » de prestation ;
- les lignes purement descriptives (INCLUS, plans, mentions d'assurance, CGV…).

Note importante : certaines lignes ne sont PAS des modules (ne crée pas d'article), mais leur présence
renseigne des champs :
- « ASSEMBLAGE / DÉSASSEMBLAGE des bungalows » -> `assemble = true` sur les bungalows du groupe ;
- « OPTION / ACCESSOIRE CLIMATISATION » -> `climatisation = true` sur le bungalow juste au-dessus ;
- « ELINGAGE POINT BAS » -> `elingage_point_bas = true` (en-tête) ;
- « DOSES SUPP. POUR WC AUTONOMES » -> `doses_wc_supplementaires` (en-tête, le nombre).

N'invente rien. Si une information d'en-tête manque, laisse le champ vide.
"""


def _appel_anthropic(pdf_bytes: bytes) -> dict:
    """Appel réel à l'API Anthropic. Renvoie le dict d'arguments de l'outil."""
    import anthropic  # import local : non requis en mode fixture

    reglages = get_reglages()
    if not reglages.anthropic_api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY manquante. Renseignez-la dans .env, ou utilisez le mode démo (fixture)."
        )

    client = anthropic.Anthropic(api_key=reglages.anthropic_api_key)
    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("ascii")

    reponse = client.messages.create(
        model=reglages.modele_extraction,
        max_tokens=16000,  # relevé pour les gros devis (évite une lecture tronquée)
        temperature=0,  # lecture = recopie déterministe (pas de variabilité d'un run à l'autre)
        system=SYSTEME,
        tools=[
            {
                "name": NOM_OUTIL,
                "description": "Enregistre l'en-tête et les articles extraits du devis.",
                "input_schema": ExtractionDevis.model_json_schema(),
            }
        ],
        tool_choice={"type": "tool", "name": NOM_OUTIL},
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": "Lis ce devis et appelle `enregistrer_devis` avec l'extraction complète.",
                    },
                ],
            }
        ],
    )

    # Garde-fou : si la réponse a été coupée (limite de longueur), l'extraction est INCOMPLÈTE
    # (des modules peuvent manquer sans erreur). On refuse plutôt que de produire un document faux.
    if getattr(reponse, "stop_reason", None) == "max_tokens":
        raise RuntimeError(
            "Le devis est trop volumineux : la lecture a été tronquée et des modules ont pu être "
            "omis. Traitez le devis en deux fois, ou prévenez l'administrateur."
        )

    for bloc in reponse.content:
        if getattr(bloc, "type", None) == "tool_use" and bloc.name == NOM_OUTIL:
            return bloc.input
    raise RuntimeError("L'extraction n'a pas renvoyé d'appel d'outil exploitable.")


def extraire_depuis_pdf(pdf_bytes: bytes) -> ExtractionDevis:
    """Lit un devis PDF et renvoie l'extraction validée (Pydantic)."""
    brut = _appel_anthropic(pdf_bytes)
    try:
        return ExtractionDevis.model_validate(brut)
    except ValidationError as exc:
        champs = ", ".join(".".join(str(p) for p in e["loc"]) for e in exc.errors()[:5])
        raise ValueError(
            "Le devis n'a pas pu être structuré correctement (champs manquants ou invalides : "
            f"{champs}). Vérifiez que le PDF est bien un devis GB lisible."
        ) from exc


def charger_fixture(nom: str = "eiffage_extraction.json") -> ExtractionDevis:
    """Charge une extraction pré-calculée (mode démo, sans appel API)."""
    chemin: Path = FIXTURES_DIR / nom
    try:
        data = json.loads(chemin.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError("Fixture de démonstration introuvable sur ce déploiement.") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Fixture de démonstration illisible (JSON invalide) : {exc}") from exc
    try:
        return ExtractionDevis.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"Fixture de démonstration non conforme : {exc.errors()[:3]}") from exc
