# Mise en ligne de l'application — guide complet (serveur français)

> Objectif : l'application tourne 24h/24 sur un petit serveur en France, en HTTPS, à l'adresse
> `https://app.gb-location.fr`. Les chauffeurs s'y connectent **en 4G depuis le chantier** et
> l'installent comme une app sur leur téléphone. Le bureau y travaille depuis son navigateur.
> Le poste de bureau n'a plus besoin de rester allumé.

---

## 1. Ce qu'il faut commander (à faire par la direction — ~15 min)

| Quoi | Où | Prix (2026) | Choix conseillé |
|---|---|---|---|
| Nom de domaine | ovhcloud.com → Domaines | ~5 € HT la 1re année, ~8 € HT/an ensuite | `gb-location.fr` (ou réutiliser un domaine existant de la société) |
| Serveur (VPS) | ovhcloud.com → VPS | ~4 à 8 € HT/mois | **VPS-1** (2 vCore / 4 Go RAM / 40 Go) — largement suffisant. Système : **Debian 12**. Datacenter : **France** (Gravelines/Strasbourg). Activer l'option **sauvegarde automatique** si proposée. |

Pourquoi OVH : hébergeur **français** (données sous droit européen uniquement — argument RGPD
solide), sauvegardes et anti-DDoS inclus, tout petit prix. Alternative équivalente : Scaleway (FR)
ou Hetzner (DE).

À la commande du VPS, OVH envoie un e-mail avec **l'adresse IP du serveur** et l'accès
(utilisateur + clé/mot de passe SSH). Le garder précieusement.

> ⚠️ **Prévenir le prestataire informatique** de la société : « nous mettons notre application
> métier interne sur un VPS OVH, accessible en HTTPS sur app.gb-location.fr, comptes individuels
> et données hébergées en France ». C'est propre, et il vérifiera que le réseau du bureau
> laisse bien sortir vers ce domaine.

## 2. Pointer le domaine vers le serveur (5 min)

Dans l'espace client OVH → Domaine → Zone DNS → **Ajouter une entrée** :

- Type `A` — sous-domaine `app` — cible = **l'adresse IP du VPS**.

(Propagation : de quelques minutes à 1 h.)

## 3. Installer l'application sur le serveur (~30 min)

Depuis un poste Windows : ouvrir **PowerShell** et se connecter au serveur :

```powershell
ssh debian@IP-DU-VPS        # utilisateur exact indiqué dans l'e-mail OVH
```

Puis, sur le serveur :

```bash
sudo apt-get update && sudo apt-get install -y git rsync
git clone https://VOTRE-DEPOT/gb-etats-des-lieux.git /tmp/gb   # OU copie par scp, voir note
sudo bash /tmp/gb/deploy/installer_vps.sh app.gb-location.fr
```

> Pas de dépôt git accessible ? Depuis le poste Windows :
> `scp -r P:\Joris\gb-etats-des-lieux debian@IP-DU-VPS:/tmp/gb` (puis la commande `installer_vps.sh` ci-dessus).

Le script installe tout : Python, l'application (service qui redémarre tout seul), **Caddy**
(HTTPS automatique Let's Encrypt — aucun certificat à gérer), et la sauvegarde quotidienne.
Il **demande de créer le compte administrateur** pendant l'installation : l'application n'est
donc **jamais publiée sans authentification** (identifiant + mot de passe choisis à cet instant).

Dernière étape : renseigner la clé API dans `/opt/gb-etats/.env`
(`sudo nano /opt/gb-etats/.env`) puis `sudo systemctl restart gb-etats`.

## 4. Migrer les données du poste de bureau (10 min)

Les données actuelles (clients, historique, documents) vivent sur le poste de bureau dans
`C:\Users\<compte>\AppData\Local\GB Etats des lieux - donnees\runtime`.

Depuis PowerShell sur le poste :

```powershell
scp -r "$env:LOCALAPPDATA\GB Etats des lieux - donnees\runtime" debian@IP-DU-VPS:/tmp/runtime
```

Puis sur le serveur :

```bash
sudo systemctl stop gb-etats
sudo rsync -a /tmp/runtime/ /opt/gb-etats/runtime/
sudo chown -R gbapp:gbapp /opt/gb-etats/runtime
sudo systemctl start gb-etats
```

> Cette migration remplace la base du serveur par celle du bureau : **les comptes existants
> (dont les vôtres) reprennent le dessus** sur l'admin créé à l'installation — c'est voulu.
> Si vous ne migrez pas de base, gardez l'admin créé pendant l'installation.

> ⚠️ À partir de là, **tout le monde travaille sur `https://app.gb-location.fr`** (bureau
> compris, via le navigateur — un raccourci sur le Bureau suffit). L'ancienne application locale
> ne doit plus servir à saisir : elle deviendrait une copie divergente. La garder comme secours.

## 5. Régler l'application (5 min)

Sur `https://app.gb-location.fr`, se connecter en admin, puis **Administration** :

1. **Comptes** : créer les comptes chauffeurs (rôle « chauffeur » — ils ne voient que leurs constats).
2. **Accès à distance** : renseigner `https://app.gb-location.fr` → le **QR code** apparaît.
   Pour les chauffeurs, remettez-leur la fiche simple **`INSTALLER_SUR_TELEPHONE.md`**
   (3 étapes, iPhone / Android) : ils scannent le QR, se connectent, « Ajouter à l'écran
   d'accueil », et l'app s'installe (icône GB, plein écran).
3. **E-mail** : renseigner le SMTP de la société (demander au prestataire messagerie) et faire
   « Envoyer un test ». C'est ce qui permet d'envoyer la **copie signée au client depuis le chantier**.

## 6. Mise à jour de l'application (quand une nouvelle version sort)

```bash
scp -r P:\Joris\gb-etats-des-lieux debian@IP-DU-VPS:/tmp/gb    # depuis le poste
ssh debian@IP-DU-VPS "sudo bash /tmp/gb/deploy/installer_vps.sh app.gb-location.fr"
```

Le script réinstalle le code **sans toucher** aux données (`runtime/`) ni au `.env`, puis
**redémarre le service** (`systemctl restart`) : le nouveau code est réellement appliqué.
Le compte administrateur existant est conservé (l'étape de création est ignorée).

## 7. Sauvegardes — trois filets

1. **Interne** : l'application copie sa base chaque jour (`runtime/sauvegardes`).
2. **Serveur** : `/usr/local/bin/gb-sauvegarde` (cron 03h15) → `/var/backups/gb-etats`, 30 jours.
3. **OVH** : snapshots automatiques du VPS si l'option est activée (recommandé).

Pour rapatrier une sauvegarde au bureau : `scp debian@IP-DU-VPS:/var/backups/gb-etats/gb-*.db P:\Joris\sauvegardes\`

## 8. Sécurité — ce qui est en place

- **HTTPS partout** (certificat automatique, renouvelé seul) — identifiants jamais en clair.
- **Connexion obligatoire** (page de connexion, sessions 7 jours, mots de passe hachés PBKDF2).
- **Anti-force-brute** par adresse IP réelle (`GB_PROXY_CONFIANCE=1` : l'app lit l'IP du client
  derrière Caddy, un robot ne peut pas bloquer tout le monde).
- **Rôle chauffeur** cloisonné (accès aux constats uniquement).
- **Journal d'audit** en base : connexions, signatures (avec empreinte SHA-256), envois.
- Serveur : service sans privilèges (`gbapp`), pare-feu OVH en amont, mises à jour de
  sécurité Debian automatiques (`unattended-upgrades` est actif par défaut sur les images OVH).

## 9. Vérification finale (checklist)

- [ ] `https://app.gb-location.fr` s'ouvre **depuis un téléphone en 4G** → page de connexion GB.
- [ ] Connexion admin OK, données du bureau retrouvées (clients, historique).
- [ ] Compte chauffeur : ne voit QUE « Mes constats ».
- [ ] « Ajouter à l'écran d'accueil » sur un téléphone → icône + plein écran.
- [ ] Constat test : saisie, photo, signature (nom + fonction + « lu et approuvé »), PDF.
- [ ] « Envoyer la copie signée » → e-mail reçu avec PDF + empreinte.
- [ ] Depuis le réseau du bureau, le site s'ouvre aussi (sinon : ticket au prestataire réseau).
