# Guide utilisateur — États des lieux (v2)

Logiciel de pré-remplissage automatique des états des lieux à partir d'un devis PDF,
pour loueurs de modulaires préfabriqués.

## 1. Démarrer

- Double-cliquez l'icône **« GB Etats des lieux »** sur le Bureau : l'application s'ouvre
  dans sa propre fenêtre. Le serveur démarre aussi automatiquement à chaque ouverture de session.
- Aucune installation de Python ni d'Excel n'est requise pour utiliser l'application
  (Excel n'est nécessaire que pour ouvrir les documents produits).

## 2. Générer des états des lieux

1. Onglet **Générer** → déposez le **devis PDF** → **Analyser le devis**.
2. L'écran de révision montre l'en-tête (client, chantier…) et les **modules détectés** :
   - chaque module a un **menu déroulant** avec l'état des lieux choisi automatiquement —
     corrigez-le si besoin ;
   - décochez un module pour l'exclure ; ajustez blocs et quantités de mobilier.
3. **Générer les états** → chaque document est **pré-rempli** (client, chantier, fonction
   du bungalow cochée, **mobilier du devis reporté tel quel**).
4. Boutons sur chaque état : **Constat** (mode chauffeur) · **Ouvrir** (dans Excel) ·
   **Imprimer** (imprimante par défaut, sans ouvrir Excel) · **Télécharger**. Plus, pour le lot :
   **Ouvrir le dossier** · **Tout télécharger (ZIP)**.

Le choix automatique s'améliore tout seul : quand vous corrigez un module inconnu,
la règle est **mémorisée** pour les prochains devis (onglet Modèles → Règles).

## 2 bis. Mode chauffeur (constat sur le terrain)

Sur chaque document généré, le bouton **« Constat »** ouvre le mode chauffeur :

1. **État réel** : remplissez les colonnes *Début de loc* / *Fin de loc* de chaque élément
   (panneaux, sol, prises…) — l'enregistrement écrit directement dans le document Excel.
2. **Photos** : prenez les dégâts en photo (bouton fichier = appareil photo sur tablette).
3. **Signature** : le client signe au doigt ou au stylet dans le cadre blanc, avec son nom.
4. **PDF** : « Générer le PDF » produit un constat complet (relevés + photos + signature datée).
5. **Partager** : ouvre un e-mail Outlook prérempli avec le PDF en pièce jointe
   (à défaut, le dossier du constat s'ouvre pour l'envoyer par un autre moyen).

Les pièces du constat (photos, signature, PDF) sont conservées dans le dossier du document,
et re-téléchargeables depuis l'Historique.

## 3. La base de connaissance

- **Clients** : la base apprend chaque client à partir des devis (fiche, interlocuteurs,
  chantiers, documents). Import massif possible par **CSV** (bouton dans l'onglet Clients).
- **Historique** : tous les dossiers produits, re-téléchargeables.
- **RGPD** : bouton **« Effacer ce client (RGPD) »** dans chaque fiche — efface la fiche,
  ses contacts, chantiers, devis, documents et traces du journal.

## 4. Modèles & règles (onglet Modèles)

- **Bibliothèque** : les modèles Excel utilisés (les vôtres, à l'identique : logo,
  perspectives, mise en page). Remplacez un modèle en déposant un `.xlsx` du même nom.
- **Règles de reconnaissance** : « mots-clés du devis → modèle ». Ajoutez, modifiez,
  supprimez librement — c'est vous qui pilotez la reconnaissance.

## 5. Administration (réservé aux administrateurs)

- **Société (marque blanche)** : nom affiché + logo de l'application (PNG/JPEG).
- **Comptes utilisateurs** : créez des comptes nominatifs (rôle *admin* ou *utilisateur*).
  ⚠️ Dès qu'un compte existe, **la connexion devient obligatoire pour tout le monde** ;
  créez donc **votre compte administrateur en premier**. Les administrateurs gèrent les
  comptes ; chaque action sensible est tracée au nom de son auteur.

## 6. Sauvegardes & mise à jour

- **Sauvegarde automatique** : une copie quotidienne de la base est conservée
  (`_internal\runtime\sauvegardes\`, 14 dernières). Restauration : fermer l'application,
  dézipper la sauvegarde et remplacer `_internal\runtime\gb.db`.
- **Mise à jour** : `build_exe.bat` (construction) puis `scripts\installer_local.bat`
  (déploiement). Vos données, votre clé API et votre logo sont **préservés**.

## 7. Dépannage

| Problème | Solution |
|---|---|
| La fenêtre ne s'ouvre pas | Relancez l'icône Bureau ; vérifiez qu'un antivirus ne bloque pas l'exe |
| « Lecture du devis impossible » | Vérifiez la clé API (`_internal\.env`) et la connexion Internet |
| Un module part sur le mauvais modèle | Corrigez via le menu déroulant (mémorisé), ou onglet Modèles → Règles |
| Mot de passe admin perdu | Supprimez la ligne du compte dans la table `utilisateurs` de `gb.db` (poste local) |
