# Note pour l'IT — autoriser l'application « États des lieux » dans Trend Micro

> À transmettre à la personne qui administre l'antivirus **Trend Micro Security Agent** du poste.
> Problème constaté : Trend Micro **supprime le programme `GB Etats des lieux.exe`** au moment où
> il est (re)compilé, ce qui empêche les mises à jour de l'application interne. Diagnostic confirmé
> dans le journal de compilation (« Ignoring non-existent resource …GB Etats des lieux.exe » :
> l'exécutable est créé puis effacé par l'agent avant l'assemblage final). Le comportement est
> reproductible en mode fenêtre **et** en mode console → c'est le **bootloader PyInstaller** qui est
> flaggé (faux positif « Behavior Monitoring / Predictive Machine Learning »), pas une vraie menace.

## Ce qu'il faut faire (au choix, le plus simple d'abord)

### Option A — Exclusions de dossiers (recommandé)
Dans la console Trend Micro (ou la stratégie poussée depuis le serveur d'administration), ajouter
en **exceptions d'analyse (Real-time Scan, Behavior Monitoring et Predictive Machine Learning)** :

- `P:\Joris\APPLICATION FINALE - Etat des lieux\`  ← l'application livrée (exécutée)
- `P:\Joris\gb-etats-des-lieux\`                    ← le code source / le build
- `%LOCALAPPDATA%\Temp\gb_dist\` et `%LOCALAPPDATA%\Temp\gb_work\`  ← dossiers temporaires de compilation

Et, si possible, ajouter le fichier `GB Etats des lieux.exe` à la liste **« Approved / Trusted
Programs »** (Behavior Monitoring → Exception List).

### Option B — Restaurer depuis la quarantaine
Dans la console Trend Micro → **Quarantine / Logs**, retrouver `GB Etats des lieux.exe` (détecté
récemment) et le **restaurer**, puis appliquer l'Option A pour que ça ne recommence pas.

## Pourquoi c'est sans risque
- L'application est **100 % interne** (pré-remplissage des états des lieux de GB Location), écrite
  en Python et empaquetée avec **PyInstaller** (outil standard et légitime). Aucune connexion sortante
  hors l'API d'IA utilisée pour lire les devis.
- La détection est un **faux positif de réputation** (exécutable non signé numériquement), pas une
  signature de virus connue.

## Alternative durable (si l'exclusion n'est pas souhaitée)
- **Signature de code** : signer l'exécutable avec un certificat de l'entreprise supprime le faux
  positif (coût ~100-300 €/an) — utile si l'app reste distribuée en `.exe`.
- **Hébergement serveur** : si l'application est mise sur un serveur (voir `DEPLOIEMENT_VPS.md`), il
  n'y a **plus aucun `.exe` à compiler** sur les postes → Trend Micro n'intervient jamais. C'est la
  solution qui supprime définitivement ce type de blocage.

Merci ! Contact projet côté GB : Joris.
