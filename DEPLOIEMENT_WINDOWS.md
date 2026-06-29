# Déploiement sur le serveur Windows

Guide pas-à-pas pour héberger le logiciel sur le serveur. À la fin, le logiciel tourne en
permanence et tous les postes du réseau y accèdent depuis leur navigateur.

> Ce n'est **pas** un fichier à ouvrir : c'est une application qui **tourne sur le serveur**.
> On l'installe une fois, elle démarre toute seule, et chacun l'utilise via une adresse web interne.

---

## Ce dont vous avez besoin
- Le serveur Windows (ou un PC qui reste allumé et sur le réseau).
- **Python 3.12+** : https://www.python.org/downloads/windows/
  → pendant l'installation, **cocher « Add python.exe to PATH »**.
- La clé API Anthropic (pour la lecture des devis).

---

## Étape 1 — Copier le dossier
Copiez le dossier `gb-etats-des-lieux` sur le serveur, par exemple dans `C:\GB\gb-etats-des-lieux`.

## Étape 2 — Installer (une seule fois)
Dans le dossier `scripts\`, **clic droit sur `install_windows.bat` → « Exécuter en tant
qu'administrateur »** (l'admin sert à ouvrir le pare-feu pour l'accès réseau).

Le script fait tout automatiquement :
1. vérifie Python ;
2. crée l'environnement et installe les dépendances ;
3. crée le fichier `.env` et ouvre le bloc-notes — **renseignez** :
   - `ANTHROPIC_API_KEY=...` (votre clé)
   - `GB_PASSWORD=...` (mot de passe d'accès au logiciel)
   - laissez `GB_HOST=0.0.0.0` et `GB_PORT=8000`
4. génère des modèles provisoires si le dossier `templates\` est vide ;
5. ouvre le port `8000` dans le pare-feu ;
6. lance un **diagnostic** qui confirme que tout est prêt.

## Étape 3 — Démarrage automatique au boot
Toujours dans `scripts\`, **clic droit sur `demarrer_au_demarrage.bat` → « Exécuter en tant
qu'administrateur »**. Le logiciel démarrera désormais **tout seul** à chaque démarrage du serveur.

Pour le lancer immédiatement sans redémarrer :
```
schtasks /Run /TN "GB Etats des Lieux"
```

> Variante « service » avec redémarrage automatique en cas de plantage : voir
> `scripts\install_service_windows.bat` (nécessite l'outil gratuit NSSM — https://nssm.cc).

## Étape 4 — Utiliser
- Sur le serveur : http://localhost:8000
- Depuis un autre poste du réseau : `http://IP-DU-SERVEUR:8000`
  (l'IP du serveur s'obtient avec la commande `ipconfig`).
- Identifiants : utilisateur `gb` (ou `GB_USER`) + le `GB_PASSWORD` choisi.

---

## Déposer les vrais modèles Excel
Dans le logiciel, rubrique **« Bibliothèque de modèles »** : déposez vos `.xlsx`. Un fichier de
même nom **remplace** l'ancien. Aucun redémarrage nécessaire. Pensez à ajuster les cellules dans
`config\cellules.yaml` et les correspondances dans `correspondances.csv`.

---

## Vérifier / dépanner
Relancez le diagnostic à tout moment :
```
.venv\Scripts\python.exe scripts\diagnostic.py
```

| Symptôme | Cause probable | Solution |
|---|---|---|
| `Python introuvable` | PATH non coché à l'install | Réinstaller Python en cochant « Add to PATH » |
| Inaccessible depuis un autre poste | Pare-feu | Relancer `install_windows.bat` en administrateur |
| `Port 8000 déjà utilisé` | Autre service sur 8000 | Changer `GB_PORT` dans `.env` (et relancer) |
| L'extraction échoue | Clé API absente/invalide ou quota | Vérifier `ANTHROPIC_API_KEY` dans `.env` |
| Page « ouverte » sans mot de passe | `GB_PASSWORD` vide | Renseigner `GB_PASSWORD` dans `.env`, redémarrer |

Gérer la tâche de démarrage :
```
schtasks /Query  /TN "GB Etats des Lieux"     :: état
schtasks /End    /TN "GB Etats des Lieux"     :: arrêter
schtasks /Delete /TN "GB Etats des Lieux" /F  :: supprimer
```
