"""Envoi d'e-mails (copie du constat au client) via SMTP — fonctionne partout,
y compris depuis le serveur hébergé et le téléphone d'un chauffeur.

La configuration vit dans la table `parametres` (Administration → E-mail) :
smtp_hote, smtp_port, smtp_securite (tls|ssl), smtp_utilisateur, smtp_mdp, smtp_expediteur.
Sans configuration SMTP, le poste de bureau garde le repli Outlook (brouillon local).
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from pathlib import Path

from app import coffre, db

_DELAI_S = 25


def configuration() -> dict:
    """Configuration SMTP (sans le mot de passe)."""
    return {
        "hote": db.lire_parametre("smtp_hote", "") or "",
        "port": int(db.lire_parametre("smtp_port", "587") or 587),
        "securite": db.lire_parametre("smtp_securite", "tls") or "tls",
        "utilisateur": db.lire_parametre("smtp_utilisateur", "") or "",
        "expediteur": db.lire_parametre("smtp_expediteur", "") or "",
        "configure": bool(db.lire_parametre("smtp_hote", "")),
    }


def enregistrer(corps: dict) -> None:
    """Enregistre la configuration ; un mot de passe vide conserve l'existant."""
    for cle in ("smtp_hote", "smtp_utilisateur", "smtp_expediteur"):
        db.ecrire_parametre(cle, str(corps.get(cle.replace("smtp_", "")) or "").strip())
    port = str(corps.get("port") or "587").strip()
    db.ecrire_parametre("smtp_port", port if port.isdigit() else "587")
    securite = str(corps.get("securite") or "tls").strip().lower()
    db.ecrire_parametre("smtp_securite", securite if securite in ("tls", "ssl") else "tls")
    mdp = corps.get("mdp")
    if mdp:  # jamais écrasé par un champ laissé vide ; stocké hors base (coffre local)
        coffre.ecrire("smtp_mdp", str(mdp))
        db.ecrire_parametre("smtp_mdp", "")  # purge d'un éventuel ancien stockage en base


def envoyer(destinataire: str, sujet: str, corps: str, pieces: list[Path] | None = None) -> None:
    """Envoie un e-mail (pièces jointes en option). Lève une exception parlante en cas d'échec."""
    cfg = configuration()
    if not cfg["configure"]:
        raise RuntimeError("L'envoi d'e-mail n'est pas configuré (Administration → E-mail).")
    message = EmailMessage()
    message["From"] = cfg["expediteur"] or cfg["utilisateur"]
    message["To"] = destinataire
    message["Subject"] = sujet
    message.set_content(corps)
    for piece in pieces or []:
        donnees = piece.read_bytes()
        if piece.suffix.lower() == ".pdf":
            type_p, sous_type = "application", "pdf"
        elif piece.suffix.lower() == ".xlsx":
            type_p = "application"
            sous_type = "vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            type_p, sous_type = "application", "octet-stream"
        message.add_attachment(donnees, maintype=type_p, subtype=sous_type, filename=piece.name)

    mdp = coffre.lire("smtp_mdp") or db.lire_parametre("smtp_mdp", "") or ""
    if cfg["securite"] == "ssl":
        with smtplib.SMTP_SSL(cfg["hote"], cfg["port"], timeout=_DELAI_S) as smtp:
            if cfg["utilisateur"]:
                smtp.login(cfg["utilisateur"], mdp)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(cfg["hote"], cfg["port"], timeout=_DELAI_S) as smtp:
            smtp.starttls()
            if cfg["utilisateur"]:
                smtp.login(cfg["utilisateur"], mdp)
            smtp.send_message(message)
