# Note pour le prestataire informatique — héberger l'application « États des lieux »

> À transmettre au prestataire / à l'informaticien de GB Location. Tout est fourni et scripté :
> l'installation prend une trentaine de minutes. Contact projet côté GB : Joris.

## En deux mots

Application web **interne** de GB Location : à partir d'un devis, elle pré-remplit les états des
lieux, et les chauffeurs les remplissent/signent depuis leur téléphone sur le chantier. On souhaite
l'héberger sur **un serveur de la société** (pas de cloud tiers) pour que **les données clients
restent chez nous** (RGPD).

- Technologie : **Python 3.12+ / FastAPI / SQLite** (base fichier, pas de SGBD à installer).
- Charge : quelques utilisateurs simultanés, **< 100 Mo** de données. Très léger.
- Ressources : **1 vCPU, 1–2 Go de RAM, 10 Go de disque** suffisent largement.

## Ce dont l'application a besoin

1. Un serveur **toujours allumé**, de préférence **Linux (Debian 12 ou Ubuntu 22.04+)**.
   *(Windows Server possible aussi — voir plus bas.)*
2. Un **sous-domaine** pointant vers le serveur, ex. `app.gb-location.fr`
   (enregistrement DNS **A** → IP du serveur).
3. **Flux réseau** : entrées **80 + 443** (obtention du certificat Let's Encrypt + HTTPS),
   sorties **80 + 443**.

## Installation (Linux) — clé en main

Le dépôt fourni contient tout (`deploy/installer_vps.sh`, service systemd, Caddy, sauvegardes).

```bash
# 1. Déposer le dossier sur le serveur (scp, git, ou copie), puis :
sudo bash deploy/installer_vps.sh app.gb-location.fr

# 2. Renseigner la clé API (fournie séparément par GB) dans le fichier .env créé :
sudo nano /opt/gb-etats/.env      # ligne ANTHROPIC_API_KEY=...
sudo systemctl restart gb-etats
```

Le script installe automatiquement : Python + l'application (service **systemd**, redémarrage
auto), **Caddy** (reverse-proxy + **HTTPS automatique Let's Encrypt**, renouvellement inclus),
une **sauvegarde quotidienne** locale, et **demande de créer le compte administrateur** pendant
l'installation (l'application n'est donc jamais publiée sans authentification).

Vérifications : `systemctl status gb-etats` puis ouvrir `https://app.gb-location.fr`.
Détails complets : `docs/DEPLOIEMENT_VPS.md` (migration des données existantes, sauvegardes, MAJ).

## Si le serveur est sous Windows

C'est possible également (l'application tourne nativement sous Windows). Le montage diffère :
service Windows (NSSM) + reverse-proxy HTTPS (Caddy pour Windows, ou IIS/ARR). **Dites-le nous et
nous fournissons la variante Windows** (script + procédure) plutôt que le kit Linux ci-dessus.

## Sécurité & RGPD (déjà en place dans l'application)

- **HTTPS** partout ; **comptes individuels** (mots de passe hachés PBKDF2) ; sessions signées.
- **Anti-force-brute** sur l'IP réelle du client (l'app lit `X-Forwarded-For` en aval de Caddy).
- **Journal d'audit** (connexions, signatures avec empreinte SHA-256, envois).
- **Données 100 % sur le serveur de la société** — aucun envoi à un tiers. Secrets réutilisables
  (session, mot de passe SMTP) stockés hors base et **hors sauvegardes**.

## Ce dont GB a besoin en retour

1. Le **système d'exploitation** du serveur (Linux ? Windows ?) — pour confirmer la procédure.
2. Le **sous-domaine** retenu (ex. `app.gb-location.fr`) et sa mise en DNS.
3. Un **accès** pour l'installation (ou vous l'exécutez vous-même avec le script ci-dessus).
4. La confirmation **quand c'est en ligne**, pour qu'on règle les comptes chauffeurs et l'e-mail.
